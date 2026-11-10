#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <limits.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <sched.h>
#include <signal.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

#if defined(__aarch64__)
#define KERNEL_ARCH AUDIT_ARCH_AARCH64
#elif defined(__x86_64__)
#define KERNEL_ARCH AUDIT_ARCH_X86_64
#else
#error Unsupported launcher architecture.
#endif

#define DENY(name, error)                                                        \
    BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_##name, 0, 1),                        \
    BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | (error))

static int restrict_calls(void) {
    struct sock_filter rules[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, KERNEL_ARCH, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
#if defined(__x86_64__)
        BPF_JUMP(BPF_JMP | BPF_JSET | BPF_K, 0x40000000, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        DENY(fork, EPERM),
        DENY(vfork, EPERM),
#endif
        DENY(clone3, ENOSYS),
        DENY(setsid, EPERM),
        DENY(setpgid, EPERM),
        DENY(unshare, EPERM),
        DENY(setns, EPERM),
        DENY(shmget, EPERM),
        DENY(shmat, EPERM),
        DENY(shmctl, EPERM),
        DENY(shmdt, EPERM),
        DENY(semget, EPERM),
        DENY(semop, EPERM),
        DENY(semctl, EPERM),
        DENY(semtimedop, EPERM),
        DENY(msgget, EPERM),
        DENY(msgsnd, EPERM),
        DENY(msgrcv, EPERM),
        DENY(msgctl, EPERM),
        DENY(mq_open, EPERM),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_clone, 0, 3),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[0])),
        BPF_JUMP(BPF_JMP | BPF_JSET | BPF_K, CLONE_THREAD, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
    };
    struct sock_fprog policy = {
        .len = sizeof(rules) / sizeof(rules[0]),
        .filter = rules,
    };
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) < 0) {
        return -1;
    }
    return prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &policy, 0, 0);
}

static void fail(int fd, const char *operation) {
    dprintf(fd, "%s: %s", operation, strerror(errno));
    _exit(125);
}

static void set_limit(int fd, int resource, rlim_t soft, rlim_t hard) {
    const struct rlimit limit = {soft, hard};
    if (setrlimit(resource, &limit) < 0) {
        fail(fd, "setrlimit");
    }
}

static void execute(int fd, char **argv) {
    uid_t uid = strtoul(argv[0], NULL, 10);
    gid_t gid = strtoul(argv[1], NULL, 10);
    if (chroot(argv[2]) < 0 || chdir("/work") < 0) {
        fail(fd, "chroot or chdir");
    }
    umask(0022);
    if (setgroups(0, NULL) < 0 || setresgid(gid, gid, gid) < 0 || setresuid(uid, uid, uid) < 0) {
        fail(fd, "drop privileges");
    }
    set_limit(fd, RLIMIT_CORE, 0, 0);
    set_limit(fd, RLIMIT_CPU, 5, 6);
    set_limit(fd, RLIMIT_AS, 1024L * 1024 * 1024, 1024L * 1024 * 1024);
    set_limit(fd, RLIMIT_FSIZE, 64L * 1024 * 1024, 64L * 1024 * 1024);
    if (restrict_calls() < 0) {
        fail(fd, "seccomp");
    }
    execv(argv[3], argv + 3);
    fail(fd, "exec");
}

static int wait_for(int fd, pid_t child) {
    int status;
    pid_t waited;
    do {
        waited = waitpid(child, &status, 0);
    } while (waited < 0 && errno == EINTR);
    if (waited != child) {
        fail(fd, "waitpid");
    }
    return status;
}

static void run_init(int fd, int status_fd, char **argv) {
    char path[PATH_MAX];
    int length = snprintf(path, sizeof(path), "%s/proc", argv[2]);
    if (length < 0 || (size_t)length >= sizeof(path)) {
        errno = ENAMETOOLONG;
        fail(fd, "proc path");
    }
    if (mkdir(path, 0555) < 0 ||
        mount("proc", path, "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, "hidepid=2") < 0) {
        fail(fd, "mount private proc");
    }
    pid_t child = fork();
    if (child < 0) {
        fail(fd, "fork target");
    }
    if (child == 0) {
        close(status_fd);
        execute(fd, argv);
    }
    int status = wait_for(fd, child);
    if (write(status_fd, &status, sizeof(status)) != sizeof(status)) {
        fail(fd, "write target status");
    }
    _exit(0);
}

static int run_with_proc(int fd, char **argv) {
    if (unshare(CLONE_NEWNS | CLONE_NEWPID | CLONE_NEWIPC) < 0 ||
        mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL) < 0) {
        fail(fd, "create private process namespace");
    }
    int channel[2];
    if (pipe2(channel, O_CLOEXEC) < 0) {
        fail(fd, "create status channel");
    }
    pid_t init = fork();
    if (init < 0) {
        fail(fd, "fork namespace init");
    }
    if (init == 0) {
        close(channel[0]);
        run_init(fd, channel[1], argv);
    }
    close(channel[1]);
    int init_status = wait_for(fd, init);
    int status;
    if (init_status != 0 || read(channel[0], &status, sizeof(status)) != sizeof(status)) {
        errno = EIO;
        fail(fd, "receive target status");
    }
    close(channel[0]);
    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    if (WIFSIGNALED(status)) {
        int number = WTERMSIG(status);
        signal(number, SIG_DFL);
        raise(number);
    }
    errno = EIO;
    fail(fd, "return target status");
    return 125;
}

int main(int argc, char **argv) {
    if (argc < 7) {
        return 125;
    }
    int fd = atoi(argv[2]);
    if (fcntl(fd, F_SETFD, FD_CLOEXEC) < 0) {
        fail(fd, "fcntl");
    }
    if (strcmp(argv[1], "rosetta") == 0) {
        return run_with_proc(fd, argv + 3);
    }
    execute(fd, argv + 3);
    return 125;
}
