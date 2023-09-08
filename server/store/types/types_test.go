package types

import (
	"encoding/json"
	"testing"
)

type conf struct {
	UidKey []byte `json:"uid_key"`
}

func TestUID(t *testing.T) {
	c := conf{}
	json.Unmarshal([]byte(`{"uid_key": "la6YsO+bNX/+XIkOqc5Svw=="}`), &c)
	ug := &UidGenerator{}
	ug.Init(1, c.UidKey)
	uid := ug.EncodeInt64(1167028326489919488)
	t.Log(uid.UserId())
}
