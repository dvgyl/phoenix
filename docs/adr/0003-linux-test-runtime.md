# Isolate each test inside the Linux worker

Use a long-lived Docker worker for one executable and one execution
engine. Keep the worker's root filesystem read-only. Use the default
Docker seccomp and AppArmor settings, no network, a PID limit, and a
bounded tmpfs. Send one executable and its cases to each worker. The
worker has no bind mounts and cannot read other programs or test sets.

Astra proposed Bubblewrap for per-test mount and PID namespaces. The
default Colima Docker policy rejected a nested namespace probe. Use a
separate chroot for each case with the runtime libraries and the case's
working directory. Set per-process limits and drop the target user and
group privileges before execution. Use libseccomp to restrict process
creation. Keep the trusted worker outside the chroot so that it can
collect exact process and file results. Verify this design before scoring
any benchmark.

Use Ubuntu 24.04 from a fixed OCI image digest and package snapshot.
The same image family supplies the x86-64 and AArch64 Linux runtimes.
Buildx can select the container architecture and copy pinned x86-64
libraries into the AArch64 image without running an x86-64 build stage.
Use GCC, Clang, CMake, and GNU Binutils from that snapshot to build
public fixtures. Use QEMU user mode from the snapshot as the independent
x86-64 oracle. Keep all upstream tools as separate dependencies.

Use the official GitHub Actions for checkout and report transfer. Use
Astral's setup action for uv. Pin each action to its commit. The public
workflow builds and runs on both native architectures. It compares the
hashes of their exact outcomes.
