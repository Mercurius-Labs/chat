APP_VERSION := $(shell git describe --tags --always)
DOCKER_IMAGE = asia-east2-docker.pkg.dev/crack-photon-385304/merc/chat

.PHONY: docker-build
docker-build:
	./docker-build.sh tag=$(APP_VERSION) name=$(DOCKER_IMAGE)

release:
	docker push $(DOCKER_IMAGE):$(APP_VERSION)

init:
	gcloud auth configure-docker asia-east2-docker.pkg.dev