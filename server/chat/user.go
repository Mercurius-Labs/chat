package chat

import (
	"sync"
	"time"

	"github.com/tinode/chat/server/logs"
	"github.com/tinode/chat/server/store/types"
)

var (
	Lobby *LobbyUserPool = &LobbyUserPool{
		users:         make(map[types.Uid]*User),
		matchingUsers: make(chan types.Uid, 1024),
	}
)

func init() {
	Lobby.checkMatchTimeout()
}

type UserState int

const (
	UserStateLobby    UserState = 1
	UserStateMatching UserState = 2
	UserStateMatched  UserState = 3
	UserStatePreChat  UserState = 4
	UserStateChat     UserState = 5
)

type MatchCompleteCallback func(matched bool, matchedUid types.Uid)

type User struct {
	uid         types.Uid
	state       UserState
	stateExpire time.Time

	matchCallback MatchCompleteCallback
}

func (u *User) State(n time.Time) UserState {
	if u.stateExpire.Before(n) {
		return UserStateLobby
	}
	return u.state
}

func (u *User) SetStateWithExpire(state UserState, expire time.Time) {
	u.state = state
	u.stateExpire = expire
}

func (u *User) SetState(state UserState) {
	u.state = state
	u.stateExpire = time.Now().Add(10 * time.Second)
}

type LobbyUserPool struct {
	mu    sync.Mutex
	users map[types.Uid]*User

	matchingUsers chan types.Uid
}

func (p *LobbyUserPool) AsyncMatch(asUid types.Uid, matchTime time.Duration, callback MatchCompleteCallback) error {
	now := time.Now()

	p.mu.Lock()
	defer p.mu.Unlock()
	asUser := p.GetUserOrInit(asUid)
	if state := asUser.State(now); state != UserStateLobby {
		logs.Info.Printf("user=%s state is invalid, expected=%d, actual=%d", asUid.UserId(), UserStateLobby, state)
		return types.ErrInvalidResponse
	}
	asUser.SetStateWithExpire(UserStateMatching, now.Add(matchTime))
	asUser.matchCallback = callback
	p.users[asUid] = asUser

	for _, user := range p.users {
		if user.uid != asUid && user.State(now) == UserStateMatching {
			user.SetState(UserStateMatched)
			asUser.SetState(UserStateMatched)

			go func(u1, u2 *User) {
				u1.matchCallback(true, u2.uid)
				u2.matchCallback(true, u1.uid)
			}(&User{uid: user.uid, matchCallback: user.matchCallback}, &User{uid: asUid, matchCallback: asUser.matchCallback})
			return nil
		}
	}
	select {
	case p.matchingUsers <- asUid:
	default:
		asUser.state = UserStateLobby
		go func(callback MatchCompleteCallback) {
			if callback != nil {
				callback(false, 0)
			}
		}(asUser.matchCallback)
	}

	return nil
}

func (p *LobbyUserPool) checkMatchTimeout() {
	go func() {
		for uid := range p.matchingUsers {
			p.mu.Lock()
			user := p.users[uid]
			if user == nil || user.state != UserStateMatching {
				logs.Info.Printf("uid=%d has matched, ignore this", uid)
				p.mu.Unlock()
				continue
			}
			delta := time.Until(user.stateExpire)
			p.mu.Unlock()

			time.Sleep(delta)

			p.mu.Lock()
			if user.state == UserStateMatching {
				user.state = UserStateLobby
				go func(callback MatchCompleteCallback) {
					if callback != nil {
						callback(false, 0)
					}
				}(user.matchCallback)
			}
			p.mu.Unlock()
		}
	}()
}

func (p *LobbyUserPool) TryP2PChat(asUid types.Uid, targetUid types.Uid) error {
	now := time.Now()
	p.mu.Lock()
	defer p.mu.Unlock()
	asUser := p.GetUserOrInit(asUid)
	if asUid == targetUid { // user triggered, update this state anyway
		logs.Info.Printf("user=%s state is invalid, expected=%d, actual=%d", asUid.UserId(), UserStateLobby, asUser.state)
		return types.ErrInvalidResponse
	}
	if targetUser := p.GetUserOrInit(targetUid); targetUser.State(now) != UserStateLobby && targetUser.state != UserStatePreChat {
		logs.Info.Printf("user=%s state is invalid, expected=Lobby || PreChat, actual=%d", targetUid.UserId(), targetUser.state)
		return types.ErrInvalidResponse
	}
	asUser.SetState(UserStatePreChat)
	return nil
}

func (p *LobbyUserPool) StartChat(asUid types.Uid) {
	p.mu.Lock()
	defer p.mu.Unlock()
	asUser := p.GetUserOrInit(asUid)
	asUser.SetStateWithExpire(UserStateChat, time.Now().Add(24*time.Hour))
}

func (p *LobbyUserPool) Leave(asUid types.Uid) {
	p.mu.Lock()
	defer p.mu.Unlock()
	delete(p.users, asUid)
}

func (p *LobbyUserPool) GetUserOrInit(asUid types.Uid) *User {
	if u, exists := p.users[asUid]; exists {
		return u
	}

	p.users[asUid] = &User{uid: asUid, state: UserStateLobby}
	return p.users[asUid]
}
