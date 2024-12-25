FROM scratch
CMD ["/sbin/init"]

# variable to store base image filename
ARG BASE_IMAGE_FILENAME=openwrt-23.05.5-x86-64-rootfs.tar.gz

# copy base image to container
ADD $BASE_IMAGE_FILENAME /

# remove and add packages
RUN --mount=type=tmpfs,target=/var/lock opkg remove procd-ujail
RUN --mount=type=tmpfs,target=/var/lock opkg update && \
    opkg install tcpdump wireless-regdb wpad-mesh kmod-mac80211 kmod-cfg80211

# disable unnecessary services
RUN --mount=type=tmpfs,target=/var/lock \
    /etc/init.d/gpio_switch disable && \    
    /etc/init.d/sysfixtime disable && \
    /etc/init.d/sysntpd disable && \
    /etc/init.d/urandom_seed disable

# copy additional files to container
COPY ./root/ /
