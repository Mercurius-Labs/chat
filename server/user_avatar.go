package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/VictoriaMetrics/fastcache"
	"github.com/tinode/chat/server/store"
	"github.com/tinode/chat/server/store/types"
)

var UserBasicInfoSvc = UserInfoService{cache: fastcache.New(32 * 1024 * 1024)}

type UserInfo struct {
	UserID   int64  `json:"user_id"`
	Avatar   string `json:"avatar"`
	Nickname string `json:"nickname"`
	Email    string `json:"email"`

	expired time.Time `json:"-"`
}

func (i *UserInfo) IsExpired() bool {
	return time.Since(i.expired) > 0
}

type UserInfoService struct {
	Host  string
	cache *fastcache.Cache
}

func (s *UserInfoService) GetFromCacheOnly(uid types.Uid) (*UserInfo, bool) {
	userInfoBytes := s.cache.Get(nil, []byte(uid.UserId()))
	if len(userInfoBytes) <= 0 {
		return nil, false
	}
	userInfo := &UserInfo{}
	if err := json.Unmarshal(userInfoBytes, userInfo); err != nil {
		return nil, false
	}
	return userInfo, true
}

func (s *UserInfoService) GetFromCacheFirst(uid types.Uid) (*UserInfo, error) {
	userInfo, exists := s.GetFromCacheOnly(uid)
	if exists && !userInfo.IsExpired() {
		return userInfo, nil
	}
	remoteUserInfo, err := s.getUserInfo(uid)
	if err != nil {
		if userInfo != nil {
			return userInfo, nil
		}
		return nil, err
	}
	remoteUserInfo.expired = time.Now().Add(24 * time.Hour)
	userInfoBytes, err := json.Marshal(remoteUserInfo)
	if err != nil {
		return remoteUserInfo, nil
	}
	s.cache.Set([]byte(uid.UserId()), userInfoBytes)
	return remoteUserInfo, nil
}

func (s *UserInfoService) getUserInfo(uid types.Uid) (*UserInfo, error) {
	user, err := store.Users.Get(uid)
	if err != nil {
		return nil, err
	}
	public, ok := user.Public.(map[string]string)
	if !ok {
		return nil, fmt.Errorf("unexcepted, unknown types for public")
	}
	url := s.Host + "?user_id=" + public["fn"]
	resp, err := http.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("get user info failed, http status=%d", resp.StatusCode)
	}
	info := &UserInfo{}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if err := json.Unmarshal(body, info); err != nil {
		return nil, err
	}
	return info, nil
}
