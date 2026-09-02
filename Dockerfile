FROM ros:jazzy-ros-base-noble

ARG ROS_DISTRO=jazzy
ARG DEV_USER
ARG DEV_UID
ARG DEV_GID

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ros-jazzy-desktop-full \
        ros-dev-tools \
        python3-vcstool \
        python3-colcon-common-extensions \
        git \
        sudo \
        bash-completion \
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
