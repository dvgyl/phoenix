# Keep the Phoenix workspace on the external drive

The host reports `arm64`, macOS 27.0.1, build 26A434, eight CPUs, and
17,179,869,184 bytes of memory. The external drive uses exFAT. A 60 GiB
case-sensitive APFS sparse bundle stores the workspace on that drive. The
bundle mounts at `/Volumes/PhoenixWork`.

The workspace script points Python, Colima, Lima, Docker, and build caches
to that mount. It checks the mount before it creates directories. The
Colima VM can use four CPUs and 6 GiB of memory. It uses a separate Docker
endpoint and does not select a new default Docker context.

The host already had Colima 0.10.3, Lima 2.2.1, Docker CLI 29.7.2, and
uv 0.12.3. The setup installed Rosetta 2 because the host could not
execute Intel code. Rosetta is an Apple system component. The Rosetta package paths use about 904 KiB of allocated storage. Some
paths are links to components supplied with macOS.
