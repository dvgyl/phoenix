#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/ipc.h>
#include <sys/resource.h>
#include <sys/shm.h>
#include <sys/stat.h>
#include <unistd.h>

int main(int argc, char **argv) {
    if (argc == 1) {
        puts(argv[0]);
        return 0;
    }
    if (strcmp(argv[1], "escape") == 0) {
        if (access("/proc/1", F_OK) == 0 || access("/opt/phoenix", F_OK) == 0 ||
            access("/work/../../opt/phoenix", F_OK) == 0 || access("/scratch", F_OK) == 0) {
            return 4;
        }
        if (fork() >= 0 || errno != EPERM) {
            return 5;
        }
        return open("/program", O_WRONLY) == -1 ? 0 : 6;
    }
    if (strcmp(argv[1], "wait") == 0) {
        for (;;) {
            pause();
        }
    }
    if (strcmp(argv[1], "policy") == 0) {
        struct rlimit cpu;
        struct rlimit memory;
        struct rlimit file;
        if (getrlimit(RLIMIT_CPU, &cpu) || getrlimit(RLIMIT_AS, &memory) ||
            getrlimit(RLIMIT_FSIZE, &file)) {
            return 8;
        }
        if (cpu.rlim_cur != 5 || memory.rlim_max != 1024L * 1024 * 1024 ||
            file.rlim_max != 64L * 1024 * 1024) {
            return 9;
        }
        if (shmget(IPC_PRIVATE, 64, IPC_CREAT | 0600) >= 0 || errno != EPERM) {
            return 10;
        }
        return 0;
    }
    if (strcmp(argv[1], "signal") == 0) {
        raise(SIGTERM);
        return 7;
    }
    if (strcmp(argv[1], "fifo") == 0) {
        return mkfifo("pipe", 0600);
    }
    return 143;
}
