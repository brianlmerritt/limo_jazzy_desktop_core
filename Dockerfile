FROM ros:humble-ros-base-jammy

ARG ROS_DISTRO=humble
ARG DEV_USER
ARG DEV_UID
ARG DEV_GID

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ros-humble-desktop \
        ros-dev-tools \
        python3-vcstool \
        python3-colcon-common-extensions \
        build-essential \
        cmake \
        git \
        sudo \
        bash-completion \
        libssl-dev \
        libusb-1.0-0-dev \
        libudev-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# RealSense ROS wrapper dependency not included in ros-humble-desktop.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ros-humble-diagnostic-updater \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    if getent group "${DEV_GID}" >/dev/null; then \
        DEV_GROUP="$(getent group "${DEV_GID}" | cut -d: -f1)"; \
    else \
        groupadd --gid "${DEV_GID}" "${DEV_USER}"; \
        DEV_GROUP="${DEV_USER}"; \
    fi; \
    useradd \
        --uid "${DEV_UID}" \
        --gid "${DEV_GROUP}" \
        --create-home \
        --shell /bin/bash \
        "${DEV_USER}"; \
    echo "${DEV_USER} ALL=(ALL) NOPASSWD:ALL" \
        > "/etc/sudoers.d/${DEV_USER}"; \
    chmod 0440 "/etc/sudoers.d/${DEV_USER}"

RUN echo "source /opt/ros/${ROS_DISTRO}/setup.bash" \
    >> /etc/bash.bashrc

ENV DEBIAN_FRONTEND=dialog

WORKDIR /workspace

USER ${DEV_USER}

CMD ["bash"]
