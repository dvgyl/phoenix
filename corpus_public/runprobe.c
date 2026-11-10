#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
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
    if (strcmp(argv[1], "signal") == 0) {
        raise(SIGTERM);
        return 7;
    }
    if (strcmp(argv[1], "fifo") == 0) {
        return mkfifo("pipe", 0600);
    }
    return 143;
}
