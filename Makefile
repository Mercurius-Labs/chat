APP_VERSION := $(shell git describe --tags --always)
DOCKER_IMAGE = asia-east2-docker.pkg.dev/crack-photon-385304/merc/chat

.PHONY: docker-build
docker-build:
	./docker-build.sh tag=$(APP_VERSION) name=$(DOCKER_IMAGE)

release:
	docker tag $(DOCKER_IMAGE):$(APP_VERSION)  $(DOCKER_IMAGE):latest
	docker push $(DOCKER_IMAGE):$(APP_VERSION)
	docker push $(DOCKER_IMAGE):latest

init:
	gcloud auth configure-docker asia-east2-docker.pkg.dev