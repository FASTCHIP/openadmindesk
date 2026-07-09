# Project Brief

## Name

OpenAdminDesk.

## Problem

Linux administrators often combine many tools: terminal emulator, SSH config,
SFTP client, tunnel commands, credential notes, X11 forwarding commands, and
remote desktop launchers. This creates friction, especially when switching
between many hosts and accounts.

## Product Goal

Create a Linux-native desktop workbench that keeps remote administration tasks
in one organized, modern, scalable application:

- session profiles,
- account and credential manager,
- connection tree,
- tabbed terminals,
- file transfer,
- port forwards,
- X11 forwarding and local X server orchestration,
- command snippets,
- per-project workspaces.

## Target Platforms

- Ubuntu LTS desktop.
- Debian-compatible systems when practical.
- Red Hat family desktop systems: RHEL, Rocky Linux, AlmaLinux, Fedora.

## Target User

System administrators, DevOps engineers, support engineers, and power users who
work with many Linux servers over SSH.

## Non-Goals

- Do not clone proprietary UI or assets.
- Do not implement a new SSH protocol stack in the MVP.
- Do not support Windows or macOS in the MVP.
- Do not build a browser-based control panel first; this is a desktop tool.
- Do not use proprietary binaries or extracted assets.

## Success Criteria for MVP

- A user can create and save SSH profiles.
- A user can organize profiles in a connection tree.
- A user can open several terminal tabs from saved profiles.
- A user can browse remote files for a selected profile.
- A user can configure local, remote, and dynamic port forwards.
- A user can store credentials in an encrypted local vault protected by a master
  password.
- A user can enable SSH X11 forwarding for a remote graphical application when
  the local environment supports it.
- The application can be installed on at least one Ubuntu LTS and one RHEL-like
  distribution.

