FROM scratch
CMD ["/sbin/init"]

# variable to store base image filename
ARG BASE_IMAGE_FILENAME=openwrt-23.05.5-x86-64-rootfs.tar.gz

# copy base image to container
ADD $BASE_IMAGE_FILENAME /

# copy additional files to container
COPY ./root/ /

# remove and add packages
RUN --mount=type=tmpfs,target=/var/lock opkg remove procd-ujail
RUN --mount=type=tmpfs,target=/var/lock opkg update && opkg install coreutils-ls mount-utils
