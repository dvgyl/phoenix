#define _POSIX_C_SOURCE 200809L
#include "color.h"
#include <getopt.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

static int coordinate(FILE *input, int *value)
{
    return int_token(input, value) && *value >= -64 && *value <= 64;
}

static int draw_command(FILE *input, struct Canvas *canvas, const char *command)
{
    int x0;
    int y0;
    int x1 = 0;
    int y1 = 0;
    struct Color color;
    if (!coordinate(input, &x0) || !coordinate(input, &y0))
        return image_error("Invalid drawing origin");
    if (!strcmp(command, "line") || !strcmp(command, "rect") || !strcmp(command, "box"))
    {
        if (!coordinate(input, &x1) || !coordinate(input, &y1))
            return image_error("Invalid drawing endpoint");
    }
    else if (!strcmp(command, "circle") || !strcmp(command, "disk"))
    {
        if (!int_token(input, &x1) || x1 < 0 || x1 > 64)
            return image_error("Invalid disk radius");
    }
    if (!color_token(input, &color))
        return image_error("Invalid drawing color");
    if (!strcmp(command, "dot"))
        draw_pixel(canvas, x0, y0, color);
    else if (!strcmp(command, "line"))
        draw_line(canvas, x0, y0, x1, y1, color);
    else if (!strcmp(command, "rect") || !strcmp(command, "box"))
        draw_rectangle(canvas, x0, y0, x1, y1, color, !strcmp(command, "box"));
    else if (!strcmp(command, "circle") || !strcmp(command, "disk"))
        draw_disk(canvas, x0, y0, x1, color, !strcmp(command, "disk"));
    else
        flood_fill(canvas, x0, y0, color);
    return 0;
}

static int blend(FILE *input, struct Canvas *canvas)
{
    struct Color color;
    int alpha;
    if (!color_token(input, &color) || !int_token(input, &alpha) || alpha < 0 || alpha > 255)
        return image_error("Invalid blend parameters");
    for (unsigned i = 0; i < canvas->width * canvas->height; i++)
    {
        struct Color *pixel = &canvas->pixels[i];
        pixel->red = (pixel->red * (255 - alpha) + color.red * alpha + 127) / 255;
        pixel->green = (pixel->green * (255 - alpha) + color.green * alpha + 127) / 255;
        pixel->blue = (pixel->blue * (255 - alpha) + color.blue * alpha + 127) / 255;
    }
    return 0;
}

static int replace(FILE *input, struct Canvas *canvas)
{
    struct Color source;
    struct Color target;
    int tolerance;
    if (!color_token(input, &source) || !color_token(input, &target) ||
        !int_token(input, &tolerance) || tolerance < 0 || tolerance > 765)
        return image_error("Invalid replacement parameters");
    unsigned count = 0;
    for (unsigned i = 0; i < canvas->width * canvas->height; i++)
    {
        struct Color color = canvas->pixels[i];
        int distance = abs(color.red - source.red) + abs(color.green - source.green) +
            abs(color.blue - source.blue);
        if (distance <= tolerance)
        {
            canvas->pixels[i] = target;
            count++;
        }
    }
    printf("replaced %u\n", count);
    return 0;
}

static int gradient(FILE *input, struct Canvas *canvas)
{
    struct Color left;
    struct Color right;
    int vertical;
    if (!color_token(input, &left) || !color_token(input, &right) ||
        !int_token(input, &vertical) || vertical < 0 || vertical > 1)
        return image_error("Invalid gradient parameters");
    unsigned span = vertical ? canvas->height : canvas->width;
    if (span > 1)
        span--;
    for (unsigned y = 0; y < canvas->height; y++)
    {
        for (unsigned x = 0; x < canvas->width; x++)
        {
            unsigned position = vertical ? y : x;
            struct Color color;
            color.red = (left.red * (int)(span - position) + right.red * (int)position) / (int)span;
            color.green = (left.green * (int)(span - position) + right.green * (int)position) / (int)span;
            color.blue = (left.blue * (int)(span - position) + right.blue * (int)position) / (int)span;
            canvas->pixels[y * canvas->width + x] = color;
        }
    }
    return 0;
}

static int mosaic(FILE *input, struct Canvas *canvas)
{
    int width;
    if (!int_token(input, &width) || width < 1 || width > 32)
        return image_error("Invalid mosaic width");
    unsigned block = (unsigned)width;
    for (unsigned y = 0; y < canvas->height; y += block)
    {
        for (unsigned x = 0; x < canvas->width; x += block)
        {
            struct Color sum = {0, 0, 0};
            unsigned count = 0;
            for (unsigned dy = 0; dy < block && y + dy < canvas->height; dy++)
            {
                for (unsigned dx = 0; dx < block && x + dx < canvas->width; dx++)
                {
                    struct Color pixel = canvas->pixels[(y + dy) * canvas->width + x + dx];
                    sum.red += pixel.red;
                    sum.green += pixel.green;
                    sum.blue += pixel.blue;
                    count++;
                }
            }
            sum.red /= (int)count;
            sum.green /= (int)count;
            sum.blue /= (int)count;
            for (unsigned dy = 0; dy < block && y + dy < canvas->height; dy++)
            {
                for (unsigned dx = 0; dx < block && x + dx < canvas->width; dx++)
                    canvas->pixels[(y + dy) * canvas->width + x + dx] = sum;
            }
        }
    }
    return 0;
}

static int paste(FILE *input, struct Canvas *canvas)
{
    char path[256];
    int x;
    int y;
    if (fscanf(input, "%255s", path) != 1 || !coordinate(input, &x) || !coordinate(input, &y))
        return image_error("Invalid paste parameters");
    struct Canvas source;
    int result = load_canvas(path, &source);
    if (result)
        return result;
    for (unsigned row = 0; row < source.height; row++)
    {
        for (unsigned column = 0; column < source.width; column++)
            draw_pixel(canvas, x + (int)column, y + (int)row, source.pixels[row * source.width + column]);
    }
    return 0;
}

struct PaletteEntry
{
    struct Color color;
    unsigned count;
};

static int palette_compare(const void *a, const void *b)
{
    const struct PaletteEntry *left = a;
    const struct PaletteEntry *right = b;
    if (left->count != right->count)
        return (left->count < right->count) - (left->count > right->count);
    if (left->color.red != right->color.red)
        return left->color.red - right->color.red;
    if (left->color.green != right->color.green)
        return left->color.green - right->color.green;
    return left->color.blue - right->color.blue;
}

static void palette_report(const struct Canvas *canvas)
{
    struct PaletteEntry entries[PIXELS];
    unsigned used = 0;
    for (unsigned i = 0; i < canvas->width * canvas->height; i++)
    {
        unsigned j;
        for (j = 0; j < used; j++)
        {
            if (color_equal(entries[j].color, canvas->pixels[i]))
                break;
        }
        if (j == used)
        {
            entries[used].color = canvas->pixels[i];
            entries[used].count = 0;
            used++;
        }
        entries[j].count++;
    }
    qsort(entries, used, sizeof(*entries), palette_compare);
    printf("palette %u\n", used);
    for (unsigned i = 0; i < used; i++)
    {
        printf("%d %d %d %u\n", entries[i].color.red, entries[i].color.green,
            entries[i].color.blue, entries[i].count);
    }
}

static void auto_levels(struct Canvas *canvas)
{
    int low[3] = {255, 255, 255};
    int high[3] = {0, 0, 0};
    for (unsigned i = 0; i < canvas->width * canvas->height; i++)
    {
        int values[3] = {canvas->pixels[i].red, canvas->pixels[i].green, canvas->pixels[i].blue};
        for (unsigned channel = 0; channel < 3; channel++)
        {
            if (values[channel] < low[channel])
                low[channel] = values[channel];
            if (values[channel] > high[channel])
                high[channel] = values[channel];
        }
    }
    for (unsigned i = 0; i < canvas->width * canvas->height; i++)
    {
        int values[3] = {canvas->pixels[i].red, canvas->pixels[i].green, canvas->pixels[i].blue};
        for (unsigned channel = 0; channel < 3; channel++)
        {
            if (low[channel] != high[channel])
                values[channel] = (values[channel] - low[channel]) * 255 / (high[channel] - low[channel]);
        }
        struct Color result = {values[0], values[1], values[2]};
        canvas->pixels[i] = result;
    }
}

static int threshold_bounds(FILE *input, struct Canvas *canvas)
{
    int threshold;
    if (!int_token(input, &threshold) || threshold < 0 || threshold > 255)
        return image_error("Invalid bounds threshold");
    unsigned count = 0;
    unsigned min_x = canvas->width;
    unsigned min_y = canvas->height;
    unsigned max_x = 0;
    unsigned max_y = 0;
    for (unsigned y = 0; y < canvas->height; y++)
    {
        for (unsigned x = 0; x < canvas->width; x++)
        {
            if (brightness(canvas->pixels[y * canvas->width + x]) < threshold)
                continue;
            count++;
            if (x < min_x)
                min_x = x;
            if (y < min_y)
                min_y = y;
            if (x > max_x)
                max_x = x;
            if (y > max_y)
                max_y = y;
        }
    }
    if (!count)
    {
        puts("bounds empty");
        return 0;
    }
    printf("bounds %u %u %u %u count %u\n", min_x, min_y, max_x, max_y, count);
    return 0;
}

int interpret(FILE *input, struct Canvas *canvas)
{
    char command[80];
    unsigned count = 0;
    while (fscanf(input, "%79s", command) == 1)
    {
        if (++count > 4096)
            return image_error("Image command limit exceeded");
        if (simple_filter(canvas, command))
            continue;
        int result = 0;
        if (!strcmp(command, "palette"))
            palette_report(canvas);
        else if (!strcmp(command, "autolevel"))
            auto_levels(canvas);
        else if (!strcmp(command, "bounds"))
            result = threshold_bounds(input, canvas);
        else if (!strcmp(command, "stats"))
            color_statistics(canvas);
        else if (!strcmp(command, "histogram"))
            color_histogram(canvas);
        else if (!strcmp(command, "dither"))
            ordered_dither(canvas);
        else if (!strcmp(command, "dot") || !strcmp(command, "line") ||
                 !strcmp(command, "rect") || !strcmp(command, "box") ||
                 !strcmp(command, "circle") || !strcmp(command, "disk") ||
                 !strcmp(command, "flood"))
            result = draw_command(input, canvas, command);
        else if (!strcmp(command, "blend"))
            result = blend(input, canvas);
        else if (!strcmp(command, "replace"))
            result = replace(input, canvas);
        else if (!strcmp(command, "gradient"))
            result = gradient(input, canvas);
        else if (!strcmp(command, "mosaic"))
            result = mosaic(input, canvas);
        else if (!strcmp(command, "paste"))
            result = paste(input, canvas);
        else if (!strcmp(command, "crop"))
        {
            int x;
            int y;
            int width;
            int height;
            if (!int_token(input, &x) || !int_token(input, &y) ||
                !int_token(input, &width) || !int_token(input, &height))
                return image_error("Missing crop parameters");
            result = crop_canvas(canvas, x, y, width, height);
        }
        else if (!strcmp(command, "resize"))
        {
            int width;
            int height;
            if (!int_token(input, &width) || !int_token(input, &height))
                return image_error("Missing resize dimensions");
            result = resize_canvas(canvas, (unsigned)width, (unsigned)height);
        }
        else if (!strcmp(command, "mirror"))
        {
            int vertical;
            if (!int_token(input, &vertical) || vertical < 0 || vertical > 1)
                return image_error("Invalid mirror axis");
            mirror_canvas(canvas, vertical);
        }
        else if (!strcmp(command, "turn"))
        {
            int turns;
            if (!int_token(input, &turns))
                return image_error("Missing turn count");
            turn_canvas(canvas, turns);
        }
        else if (!strcmp(command, "kernel") || !strcmp(command, "quantize") || !strcmp(command, "cluster"))
        {
            int value;
            if (!int_token(input, &value))
                return image_error("Missing integer filter value");
            if (!strcmp(command, "kernel"))
                result = convolve(canvas, value);
            else if (!strcmp(command, "quantize"))
            {
                if (value < 2 || value > 256)
                    return image_error("Invalid quantization level");
                quantize(canvas, value);
            }
            else
            {
                if (value < 1 || value > 16)
                    return image_error("Invalid cluster count");
                cluster_palette(canvas, (unsigned)value);
            }
        }
        else if (!strcmp(command, "hue") || !strcmp(command, "saturation") ||
                 !strcmp(command, "value") || !strcmp(command, "bias") ||
                 !strcmp(command, "contrast") || !strcmp(command, "gamma"))
        {
            double value;
            if (!real_token(input, &value))
                return image_error("Invalid real filter value");
            int mode = !strcmp(command, "hue") ? 0 : !strcmp(command, "saturation") ? 1 :
                !strcmp(command, "value") ? 2 : !strcmp(command, "bias") ? 3 :
                !strcmp(command, "contrast") ? 4 : 5;
            if (mode == 5 && value <= 0)
                return image_error("Gamma must be positive");
            color_adjust(canvas, mode, value);
        }
        else if (!strcmp(command, "save") || !strcmp(command, "load"))
        {
            char path[256];
            if (fscanf(input, "%255s", path) != 1)
                return image_error("Missing canvas path");
            if (!strcmp(command, "save"))
                result = save_canvas(path, canvas, 0);
            else
                result = load_canvas(path, canvas);
        }
        else
            return image_error("Unknown canvas command");
        if (result)
            return result;
    }
    return 0;
}

int main(int argc, char **argv)
{
    struct Settings settings = {0, 0, 0, NULL};
    int option;
    opterr = 0;
    while ((option = getopt(argc, argv, "qgro:")) != -1)
    {
        switch (option)
        {
            case 'q':
                settings.quiet = 1;
                break;
            case 'g':
                settings.format = 1;
                break;
            case 'r':
                settings.report = 1;
                break;
            case 'o':
                settings.output = optarg;
                break;
            default:
                return image_error("Invalid option");
        }
    }
    if (argc - optind > 1)
        return image_error("Too many files");
    FILE *input = stdin;
    if (optind < argc)
    {
        input = fopen(argv[optind], "r");
        if (!input)
            return image_error("Cannot open input");
    }
    struct Canvas canvas;
    int result = read_canvas(input, &canvas);
    if (!result)
        result = interpret(input, &canvas);
    if (input != stdin)
        fclose(input);
    if (result)
        return result;
    if (settings.report)
        color_statistics(&canvas);
    if (settings.output)
        return save_canvas(settings.output, &canvas, settings.format);
    if (!settings.quiet)
        write_canvas(stdout, &canvas, settings.format);
    return 0;
}
