package merc

import (
	"encoding/json"
	"time"

	"github.com/tinode/chat/server/auth"
	"github.com/tinode/chat/server/logs"
	"github.com/tinode/chat/server/store"
	"github.com/tinode/chat/server/store/types"
	"golang.org/x/crypto/bcrypt"
)

const (
	realName = "merc"
)

type authenticator struct {
}

func (a *authenticator) Init(_ json.RawMessage, _ string) error {
	return nil
}

// IsInitialized returns true if the handler is initialized.
func (a *authenticator) IsInitialized() bool {
	return true
}

// AddRecord checks authLevel and assigns default LevelAnon. Otherwise it
// just reports success.
func (a authenticator) AddRecord(rec *auth.Rec, secret []byte, remoteAddr string) (*auth.Rec, error) {
	mercID := string(secret)

	passhash, err := bcrypt.GenerateFromPassword([]byte(mercID), bcrypt.DefaultCost)
	if err != nil {
		return nil, err
	}
	var expires time.Time
	if rec.Lifetime > 0 {
		expires = time.Now().Add(time.Duration(rec.Lifetime)).UTC().Round(time.Millisecond)
	}

	authLevel := rec.AuthLevel
	if authLevel == auth.LevelNone {
		authLevel = auth.LevelAuth
	}

	err = store.Users.AddAuthRecord(rec.Uid, authLevel, realName, mercID, passhash, expires)
	if err != nil {
		return nil, err
	}

	rec.AuthLevel = authLevel
	return rec, nil
}

// UpdateRecord is a noop. Just report success.
func (authenticator) UpdateRecord(rec *auth.Rec, secret []byte, remoteAddr string) (*auth.Rec, error) {
	return rec, types.ErrUnsupported
}

// Authenticate is not supported. This authenticator is used only at account creation time.
func (a authenticator) Authenticate(secret []byte, remoteAddr string) (*auth.Rec, []byte, error) {
	var userInfo = make(map[string]any)
	if err := json.Unmarshal(secret, &userInfo); err != nil {
		return nil, nil, err
	}
	mercID, _ := userInfo["uid"].(string)
	if mercID == "" {
		return nil, nil, types.ErrCredentials
	}
	secret = []byte(mercID)
	uid, authLvl, passhash, expires, err := store.Users.GetAuthUniqueRecord(realName, mercID)
	if err != nil {
		logs.Err.Printf("merc.Authenticate: GetAuthUniqueRecord failed, mercID=%s, err=%v", mercID, err)
		return nil, nil, err
	}
	if uid.IsZero() {
		logs.Info.Printf("merc.Authenticate: create new user, mercID=%s", mercID)
		// 创建用户
		user := &types.User{
			Access: types.DefaultAccess{
				// Auth: types.ModeCP2P | types.ModeCPublic,
				Auth: types.ModeJoin | types.ModeApprove,
				Anon: types.ModeNone,
			},
			Public: userInfo["public"],
			Tags:   []string{"merc:" + mercID},
		}
		if _, err := store.Users.Create(user, map[string]any{"uid": mercID}); err != nil {
			logs.Warn.Println("merc.Authenticate: user state check failed", user.Uid(), err)
			return nil, nil, err
		}

		rec, err := a.AddRecord(&auth.Rec{Uid: user.Uid(), Tags: user.Tags}, secret, remoteAddr)
		if err != nil {
			logs.Warn.Println("create user: add auth record failed", err)
			// Attempt to delete incomplete user record
			if e := store.Users.Delete(user.Uid(), true); e != nil {
				logs.Warn.Println("create user: failed to delete incomplete user record", e)
			}
			return nil, nil, err
		}
		return rec, nil, nil
	} else {
		// this is not affect if failed
		if e := store.Users.Update(uid, map[string]interface{}{"public": userInfo["public"]}); e != nil {
			logs.Warn.Println("update user: failed to update `public`", e)
		}
	}

	if !expires.IsZero() && expires.Before(time.Now()) {
		// The record has expired
		return nil, nil, types.ErrExpired
	}

	err = bcrypt.CompareHashAndPassword(passhash, []byte(mercID))
	if err != nil {
		// Invalid password
		return nil, nil, types.ErrFailed
	}

	var lifetime time.Duration
	if !expires.IsZero() {
		lifetime = time.Until(expires)
	}
	return &auth.Rec{
		Uid:       uid,
		AuthLevel: authLvl,
		Lifetime:  auth.Duration(lifetime),
		Features:  0,
		State:     types.StateUndefined}, nil, nil
}

// AsTag is not supported, will produce an empty string.
func (authenticator) AsTag(token string) string {
	return ""
}

// IsUnique for a noop. Anonymous login does not use secret, any secret is fine.
func (authenticator) IsUnique(secret []byte, remoteAddr string) (bool, error) {
	return true, nil
}

// GenSecret always fails.
func (authenticator) GenSecret(rec *auth.Rec) ([]byte, time.Time, error) {
	return nil, time.Time{}, types.ErrUnsupported
}

// DelRecords is a noop which always succeeds.
func (authenticator) DelRecords(uid types.Uid) error {
	return nil
}

// RestrictedTags returns tag namespaces restricted by this authenticator (none for anonymous).
func (authenticator) RestrictedTags() ([]string, error) {
	return nil, nil
}

// GetResetParams returns authenticator parameters passed to password reset handler
// (none for anonymous).
func (authenticator) GetResetParams(uid types.Uid) (map[string]interface{}, error) {
	return nil, nil
}

// GetRealName returns the hardcoded name of the authenticator.
func (authenticator) GetRealName() string {
	return realName
}

func init() {
	store.RegisterAuthScheme(realName, &authenticator{})
}
