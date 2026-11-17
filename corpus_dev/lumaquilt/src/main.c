#define _POSIX_C_SOURCE 200809L
#include <getopt.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

struct Image
{
    unsigned width;
    unsigned height;
    unsigned char pixels[1024];
};

struct Filter
{
    const char *name;
    void (*apply)(struct Image *);
};

static unsigned char clamp(int value)
{
    if (value < 0)
        return 0;
    if (value > 255)
        return 255;
    return (unsigned char)value;
}

static int integer(FILE *input, int *value)
{
    char token[80];
    char *end;
    if (fscanf(input, "%79s", token) != 1)
        return 0;
    long number = strtol(token, &end, 10);
    if (*end || number < -100000 || number > 100000)
        return 0;
    *value = (int)number;
    return 1;
}

static int read_image(FILE *input, struct Image *image)
{
    int width;
    int height;
    if (!integer(input, &width) || !integer(input, &height) ||
        width < 1 || height < 1 || width > 32 || height > 32)
    {
        fputs("Invalid image dimensions\n", stderr);
        return 3;
    }
    image->width = (unsigned)width;
    image->height = (unsigned)height;
    for (unsigned i = 0; i < image->width * image->height; i++)
    {
        int value;
        if (!integer(input, &value) || value < 0 || value > 255)
        {
            fputs("Invalid image sample\n", stderr);
            return 3;
        }
        image->pixels[i] = (unsigned char)value;
    }
    return 0;
}

static void write_image(FILE *output, const struct Image *image)
{
    fprintf(output, "%u %u\n", image->width, image->height);
    for (unsigned y = 0; y < image->height; y++)
    {
        for (unsigned x = 0; x < image->width; x++)
        {
            if (x)
                fputc(' ', output);
            fprintf(output, "%u", image->pixels[y * image->width + x]);
        }
        fputc('\n', output);
    }
}

static void invert(struct Image *image)
{
    for (unsigned i = 0; i < image->width * image->height; i++)
        image->pixels[i] = (unsigned char)(255 - image->pixels[i]);
}

static void flip_x(struct Image *image)
{
    for (unsigned y = 0; y < image->height; y++)
    {
        for (unsigned x = 0; x < image->width / 2; x++)
        {
            unsigned left = y * image->width + x;
            unsigned right = y * image->width + image->width - x - 1;
            unsigned char saved = image->pixels[left];
            image->pixels[left] = image->pixels[right];
            image->pixels[right] = saved;
        }
    }
}

static void flip_y(struct Image *image)
{
    for (unsigned y = 0; y < image->height / 2; y++)
    {
        for (unsigned x = 0; x < image->width; x++)
        {
            unsigned top = y * image->width + x;
            unsigned bottom = (image->height - y - 1) * image->width + x;
            unsigned char saved = image->pixels[top];
            image->pixels[top] = image->pixels[bottom];
            image->pixels[bottom] = saved;
        }
    }
}

static void transpose(struct Image *image)
{
    struct Image result = {image->height, image->width, {0}};
    for (unsigned y = 0; y < image->height; y++)
    {
        for (unsigned x = 0; x < image->width; x++)
            result.pixels[x * result.width + y] = image->pixels[y * image->width + x];
    }
    *image = result;
}

static void rotate(struct Image *image)
{
    transpose(image);
    flip_x(image);
}

static int sample(const struct Image *image, int x, int y)
{
    if (x < 0)
        x = 0;
    if (y < 0)
        y = 0;
    if ((unsigned)x >= image->width)
        x = (int)image->width - 1;
    if ((unsigned)y >= image->height)
        y = (int)image->height - 1;
    return image->pixels[(unsigned)y * image->width + (unsigned)x];
}

static void blur(struct Image *image)
{
    struct Image result = *image;
    for (unsigned y = 0; y < image->height; y++)
    {
        for (unsigned x = 0; x < image->width; x++)
        {
            int total = 0;
            for (int dy = -1; dy <= 1; dy++)
            {
                for (int dx = -1; dx <= 1; dx++)
                    total += sample(image, (int)x + dx, (int)y + dy);
            }
            result.pixels[y * image->width + x] = (unsigned char)((total + 4) / 9);
        }
    }
    *image = result;
}

static int compare_int(const void *a, const void *b)
{
    int left = *(const int *)a;
    int right = *(const int *)b;
    return (left > right) - (left < right);
}

static void median(struct Image *image)
{
    struct Image result = *image;
    for (unsigned y = 0; y < image->height; y++)
    {
        for (unsigned x = 0; x < image->width; x++)
        {
            int values[9];
            unsigned used = 0;
            for (int dy = -1; dy <= 1; dy++)
            {
                for (int dx = -1; dx <= 1; dx++)
                    values[used++] = sample(image, (int)x + dx, (int)y + dy);
            }
            qsort(values, 9, sizeof(int), compare_int);
            result.pixels[y * image->width + x] = (unsigned char)values[4];
        }
    }
    *image = result;
}

static void morphology(struct Image *image, int maximum)
{
    struct Image result = *image;
    for (unsigned y = 0; y < image->height; y++)
    {
        for (unsigned x = 0; x < image->width; x++)
        {
            int best = maximum ? 0 : 255;
            for (int dy = -1; dy <= 1; dy++)
            {
                for (int dx = -1; dx <= 1; dx++)
                {
                    int value = sample(image, (int)x + dx, (int)y + dy);
                    if ((maximum && value > best) || (!maximum && value < best))
                        best = value;
                }
            }
            result.pixels[y * image->width + x] = (unsigned char)best;
        }
    }
    *image = result;
}

static void erode(struct Image *image)
{
    morphology(image, 0);
}

static void dilate(struct Image *image)
{
    morphology(image, 1);
}

static void edges(struct Image *image)
{
    struct Image result = *image;
    for (unsigned y = 0; y < image->height; y++)
    {
        for (unsigned x = 0; x < image->width; x++)
        {
            int gx = sample(image, (int)x + 1, (int)y) - sample(image, (int)x - 1, (int)y);
            int gy = sample(image, (int)x, (int)y + 1) - sample(image, (int)x, (int)y - 1);
            result.pixels[y * image->width + x] = clamp(abs(gx) + abs(gy));
        }
    }
    *image = result;
}

static void normalize(struct Image *image)
{
    unsigned low = 255;
    unsigned high = 0;
    unsigned count = image->width * image->height;
    for (unsigned i = 0; i < count; i++)
    {
        unsigned value = image->pixels[i];
        if (value < low)
            low = value;
        if (value > high)
            high = value;
    }
    if (low == high)
        return;
    for (unsigned i = 0; i < count; i++)
        image->pixels[i] = (unsigned char)((image->pixels[i] - low) * 255 / (high - low));
}

static void equalize(struct Image *image)
{
    unsigned bins[256] = {0};
    unsigned count = image->width * image->height;
    for (unsigned i = 0; i < count; i++)
        bins[image->pixels[i]]++;
    unsigned sum = 0;
    for (unsigned i = 0; i < 256; i++)
    {
        sum += bins[i];
        bins[i] = sum * 255 / count;
    }
    for (unsigned i = 0; i < count; i++)
        image->pixels[i] = (unsigned char)bins[image->pixels[i]];
}

static void dither(struct Image *image)
{
    static const unsigned pattern[4] = {32, 160, 224, 96};
    for (unsigned y = 0; y < image->height; y++)
    {
        for (unsigned x = 0; x < image->width; x++)
        {
            unsigned index = y * image->width + x;
            unsigned threshold = pattern[(y % 2) * 2 + x % 2];
            image->pixels[index] = image->pixels[index] >= threshold ? 255 : 0;
        }
    }
}

static const struct Filter filters[] =
{
    {"invert", invert},
    {"flipx", flip_x},
    {"flipy", flip_y},
    {"transpose", transpose},
    {"rotate", rotate},
    {"blur", blur},
    {"median", median},
    {"erode", erode},
    {"dilate", dilate},
    {"edges", edges},
    {"normalize", normalize},
    {"equalize", equalize},
    {"dither", dither}
};

static void statistics(const struct Image *image)
{
    unsigned count = image->width * image->height;
    double sum = 0;
    double square = 0;
    unsigned nonzero = 0;
    unsigned low = 255;
    unsigned high = 0;
    for (unsigned i = 0; i < count; i++)
    {
        unsigned value = image->pixels[i];
        sum += value;
        square += value * value;
        nonzero += value != 0;
        if (value < low)
            low = value;
        if (value > high)
            high = value;
    }
    double mean = sum / count;
    double variance = square / count - mean * mean;
    if (variance < 0)
        variance = 0;
    printf("range %u %u\n", low, high);
    printf("mean %.6f\n", mean);
    printf("deviation %.6f\n", sqrt(variance));
    printf("nonzero %u\n", nonzero);
}

static void histogram(const struct Image *image)
{
    unsigned bins[16] = {0};
    for (unsigned i = 0; i < image->width * image->height; i++)
        bins[image->pixels[i] >> 4]++;
    for (unsigned i = 0; i < 16; i++)
        printf("%u %u\n", i * 16, bins[i]);
}

static int parameter_filter(struct Image *image, char command, FILE *input)
{
    int value;
    if (!integer(input, &value))
    {
        fputs("Missing filter parameter\n", stderr);
        return 3;
    }
    if (command == 'p' && (value < 2 || value > 256))
    {
        fputs("Invalid posterization level\n", stderr);
        return 3;
    }
    for (unsigned y = 0; y < image->height; y++)
    {
        for (unsigned x = 0; x < image->width; x++)
        {
            unsigned index = y * image->width + x;
            int pixel = image->pixels[index];
            switch (command)
            {
                case 'b':
                    pixel += value;
                    break;
                case 't':
                    pixel = pixel >= value ? 255 : 0;
                    break;
                case 'p':
                    pixel = (pixel * (value - 1) / 255) * 255 / (value - 1);
                    break;
                case 's':
                    if (pixel >= value)
                        pixel = 255 - pixel;
                    break;
                case 'f':
                    pixel = value;
                    break;
                case 'g':
                    pixel += (int)x * value;
                    break;
                case 'v':
                    pixel += (int)y * value;
                    break;
                case 'r':
                    if (x == 0 || y == 0 || x + 1 == image->width || y + 1 == image->height)
                        pixel = value;
                    break;
            }
            image->pixels[index] = clamp(pixel);
        }
    }
    return 0;
}

static int crop(struct Image *image, FILE *input)
{
    int x;
    int y;
    int width;
    int height;
    if (!integer(input, &x) || !integer(input, &y) ||
        !integer(input, &width) || !integer(input, &height) ||
        x < 0 || y < 0 || width < 1 || height < 1 ||
        x + width > (int)image->width || y + height > (int)image->height)
    {
        fputs("Invalid crop rectangle\n", stderr);
        return 3;
    }
    struct Image result = {(unsigned)width, (unsigned)height, {0}};
    for (int row = 0; row < height; row++)
    {
        for (int column = 0; column < width; column++)
        {
            result.pixels[(unsigned)row * result.width + (unsigned)column] =
                image->pixels[(unsigned)(y + row) * image->width + (unsigned)(x + column)];
        }
    }
    *image = result;
    return 0;
}

static int tiles(const struct Image *image, FILE *input)
{
    char directory[128];
    if (fscanf(input, "%127s", directory) != 1)
    {
        fputs("Missing tile directory\n", stderr);
        return 3;
    }
    if (mkdir(directory, 0755))
    {
        fputs("Cannot create tile directory\n", stderr);
        return 4;
    }
    for (unsigned y = 0; y < image->height; y++)
    {
        char path[192];
        snprintf(path, sizeof(path), "%s/row-%02u", directory, y);
        FILE *file = fopen(path, "w");
        if (!file)
        {
            fputs("Cannot create tile file\n", stderr);
            return 4;
        }
        struct Image row = {image->width, 1, {0}};
        memcpy(row.pixels, image->pixels + y * image->width, image->width);
        write_image(file, &row);
        fclose(file);
    }
    return 0;
}

static unsigned flood(const struct Image *image, unsigned index,
                      unsigned char *visited, unsigned threshold)
{
    if (visited[index] || image->pixels[index] < threshold)
        return 0;
    visited[index] = 1;
    unsigned area = 1;
    unsigned x = index % image->width;
    unsigned y = index / image->width;
    if (x > 0)
        area += flood(image, index - 1, visited, threshold);
    if (x + 1 < image->width)
        area += flood(image, index + 1, visited, threshold);
    if (y > 0)
        area += flood(image, index - image->width, visited, threshold);
    if (y + 1 < image->height)
        area += flood(image, index + image->width, visited, threshold);
    return area;
}

static int components(const struct Image *image, FILE *input)
{
    int threshold;
    if (!integer(input, &threshold) || threshold < 0 || threshold > 255)
    {
        fputs("Invalid component threshold\n", stderr);
        return 3;
    }
    unsigned char visited[1024] = {0};
    unsigned count = 0;
    unsigned largest = 0;
    unsigned total = 0;
    for (unsigned i = 0; i < image->width * image->height; i++)
    {
        unsigned area = flood(image, i, visited, (unsigned)threshold);
        if (!area)
            continue;
        count++;
        total += area;
        if (area > largest)
            largest = area;
        printf("component %u %u %u %u\n", count, i % image->width,
            i / image->width, area);
    }
    printf("components %u area %u largest %u\n", count, total, largest);
    return 0;
}

static void sharpen(struct Image *image)
{
    struct Image result = *image;
    for (unsigned y = 0; y < image->height; y++)
    {
        for (unsigned x = 0; x < image->width; x++)
        {
            int center = sample(image, (int)x, (int)y) * 5;
            center -= sample(image, (int)x - 1, (int)y);
            center -= sample(image, (int)x + 1, (int)y);
            center -= sample(image, (int)x, (int)y - 1);
            center -= sample(image, (int)x, (int)y + 1);
            result.pixels[y * image->width + x] = clamp(center);
        }
    }
    *image = result;
}

static void diagonal(struct Image *image)
{
    for (unsigned y = 0; y < image->height; y++)
    {
        for (unsigned x = 0; x < image->width; x++)
        {
            unsigned index = y * image->width + x;
            int value = image->pixels[index];
            if ((x + y) % 2)
                value = 255 - value;
            image->pixels[index] = (unsigned char)value;
        }
    }
}

static int commands(FILE *input, struct Image *image)
{
    char command[80];
    while (fscanf(input, "%79s", command) == 1)
    {
        unsigned i;
        for (i = 0; i < sizeof(filters) / sizeof(*filters); i++)
        {
            if (!strcmp(command, filters[i].name))
                break;
        }
        if (i < sizeof(filters) / sizeof(*filters))
        {
            filters[i].apply(image);
            continue;
        }
        int result = 0;
        if (!strcmp(command, "sharpen"))
            sharpen(image);
        else if (!strcmp(command, "diagonal"))
            diagonal(image);
        else if (!strcmp(command, "components"))
            result = components(image, input);
        else if (!strcmp(command, "stats"))
            statistics(image);
        else if (!strcmp(command, "histogram"))
            histogram(image);
        else if (!strcmp(command, "crop"))
            result = crop(image, input);
        else if (!strcmp(command, "tiles"))
            result = tiles(image, input);
        else if (strlen(command) == 1 && strchr("btpsfgvr", command[0]))
            result = parameter_filter(image, command[0], input);
        else
        {
            fputs("Invalid image command\n", stderr);
            return 3;
        }
        if (result)
            return result;
    }
    return 0;
}

int main(int argc, char **argv)
{
    int quiet = 0;
    int option;
    const char *output_path = NULL;
    opterr = 0;
    while ((option = getopt(argc, argv, "qo:")) != -1)
    {
        if (option == 'q')
        {
            quiet = 1;
        }
        else if (option == 'o')
        {
            output_path = optarg;
        }
        else
        {
            fputs("Invalid option\n", stderr);
            return 2;
        }
    }
    if (argc - optind > 1)
    {
        fputs("Too many files\n", stderr);
        return 2;
    }
    FILE *input = stdin;
    if (optind < argc)
    {
        input = fopen(argv[optind], "r");
        if (!input)
        {
            fputs("Cannot open input\n", stderr);
            return 4;
        }
    }
    struct Image image;
    int result = read_image(input, &image);
    if (!result)
        result = commands(input, &image);
    if (input != stdin)
        fclose(input);
    if (result)
        return result;
    if (output_path)
    {
        FILE *output = fopen(output_path, "w");
        if (!output)
        {
            fputs("Cannot open output\n", stderr);
            return 4;
        }
        write_image(output, &image);
        fclose(output);
    }
    else if (!quiet)
    {
        write_image(stdout, &image);
    }
    return 0;
}
