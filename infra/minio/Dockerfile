# syntax=docker/dockerfile:1
FROM golang:1.24-bookworm AS build
WORKDIR /src
# Upstream MinIO RELEASE.2025-04-22T22-12-26Z.
ARG MINIO_COMMIT=0d7408fc9969caf07de6a8c3a84f9fbb10a6739e
ARG MINIO_TIMESTAMP=2025-04-22T22-12-26Z
ADD --checksum=sha256:7eb30a913fea30f18069abf194e1e78e4983b558cc526911ae1c11396a9859a5 \
    https://codeload.github.com/minio/minio/tar.gz/${MINIO_COMMIT} /tmp/minio.tar.gz
RUN tar -xzf /tmp/minio.tar.gz --strip-components=1
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -p 2 -trimpath -tags kqueue \
    -ldflags "-s -w -X github.com/minio/minio/cmd.Version=2025-04-22T22:12:26Z \
    -X github.com/minio/minio/cmd.ReleaseTag=RELEASE.${MINIO_TIMESTAMP} \
    -X github.com/minio/minio/cmd.CommitID=${MINIO_COMMIT} \
    -X github.com/minio/minio/cmd.ShortCommitID=0d7408fc9969 \
    -X github.com/minio/minio/cmd.CopyrightYear=2025" -o /minio .

FROM scratch
COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --from=build /src/LICENSE /licenses/minio/LICENSE
COPY --from=build /minio /minio
ENTRYPOINT ["/minio"]
