#include "color.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

int image_error(const char *message)
{
    fprintf(stderr, "%s\n", message);
    return 3;
}

int int_token(FILE *input, int *value)
{
    char word[80];
    char *end;
    if (fscanf(input, "%79s", word) != 1)
        return 0;
    long parsed = strtol(word, &end, 10);
    if (*end || parsed < -10000 || parsed > 10000)
        return 0;
    *value = (int)parsed;
    return 1;
}

int real_token(FILE *input, double *value)
{
    char word[80];
    char *end;
    if (fscanf(input, "%79s", word) != 1)
        return 0;
    double parsed = strtod(word, &end);
    if (*end || !isfinite(parsed) || fabs(parsed) > 10000)
        return 0;
    *value = parsed;
    return 1;
}

int color_token(FILE *input, struct Color *color)
{
    if (!int_token(input, &color->red) || !int_token(input, &color->green) ||
        !int_token(input, &color->blue))
        return 0;
    if (color->red < 0 || color->red > 255 || color->green < 0 ||
        color->green > 255 || color->blue < 0 || color->blue > 255)
        return 0;
    return 1;
}

int read_canvas(FILE *input, struct Canvas *canvas)
{
    char format[16];
    int width;
    int height;
    if (fscanf(input, "%15s", format) != 1 ||
        (strcmp(format, "C3") && strcmp(format, "C1") && strcmp(format, "CP")))
        return image_error("Invalid canvas signature");
    if (!int_token(input, &width) || !int_token(input, &height) ||
        width < 1 || width > SIDE || height < 1 || height > SIDE)
        return image_error("Invalid canvas dimensions");
    canvas->width = (unsigned)width;
    canvas->height = (unsigned)height;
    struct Color palette[16];
    int colors = 0;
    if (!strcmp(format, "CP"))
    {
        if (!int_token(input, &colors) || colors < 1 || colors > 16)
            return image_error("Invalid palette size");
        for (int i = 0; i < colors; i++)
        {
            if (!color_token(input, &palette[i]))
                return image_error("Invalid palette color");
        }
    }
    for (unsigned i = 0; i < canvas->width * canvas->height; i++)
    {
        struct Color color;
        if (!strcmp(format, "C3"))
        {
            if (!color_token(input, &color))
                return image_error("Invalid canvas color");
        }
        else
        {
            int value;
            if (!int_token(input, &value))
                return image_error("Missing canvas sample");
            if (colors)
            {
                if (value < 0 || value >= colors)
                    return image_error("Palette index exceeds range");
                color = palette[value];
            }
            else
            {
                if (value < 0 || value > 255)
                    return image_error("Gray sample exceeds range");
                color.red = value;
                color.green = value;
                color.blue = value;
            }
        }
        canvas->pixels[i] = color;
    }
    return 0;
}

void write_canvas(FILE *output, const struct Canvas *canvas, int format)
{
    fprintf(output, "%s %u %u\n", format == 1 ? "C1" : "C3", canvas->width, canvas->height);
    for (unsigned y = 0; y < canvas->height; y++)
    {
        for (unsigned x = 0; x < canvas->width; x++)
        {
            struct Color color = canvas->pixels[y * canvas->width + x];
            if (x)
                fputc(' ', output);
            if (format == 1)
                fprintf(output, "%d", brightness(color));
            else
                fprintf(output, "%d %d %d", color.red, color.green, color.blue);
        }
        fputc('\n', output);
    }
}

int load_canvas(const char *path, struct Canvas *canvas)
{
    FILE *input = fopen(path, "r");
    if (!input)
        return image_error("Cannot open canvas input");
    int result = read_canvas(input, canvas);
    fclose(input);
    return result;
}

int save_canvas(const char *path, const struct Canvas *canvas, int format)
{
    FILE *output = fopen(path, "w");
    if (!output)
        return image_error("Cannot create canvas output");
    write_canvas(output, canvas, format);
    fclose(output);
    return 0;
}

int clamp_channel(int value)
{
    if (value < 0)
        return 0;
    if (value > 255)
        return 255;
    return value;
}

struct Color clamp_color(struct Color color)
{
    color.red = clamp_channel(color.red);
    color.green = clamp_channel(color.green);
    color.blue = clamp_channel(color.blue);
    return color;
}

int color_equal(struct Color left, struct Color right)
{
    return left.red == right.red && left.green == right.green && left.blue == right.blue;
}

int brightness(struct Color color)
{
    return (77 * color.red + 150 * color.green + 29 * color.blue + 128) / 256;
}

struct Hsv to_hsv(struct Color color)
{
    double r = color.red / 255.0;
    double g = color.green / 255.0;
    double b = color.blue / 255.0;
    double high = fmax(r, fmax(g, b));
    double low = fmin(r, fmin(g, b));
    double delta = high - low;
    struct Hsv hsv = {0, high == 0 ? 0 : delta / high, high};
    if (delta == 0)
        return hsv;
    if (high == r)
        hsv.hue = 60 * fmod((g - b) / delta, 6);
    else if (high == g)
        hsv.hue = 60 * ((b - r) / delta + 2);
    else
        hsv.hue = 60 * ((r - g) / delta + 4);
    if (hsv.hue < 0)
        hsv.hue += 360;
    return hsv;
}

struct Color from_hsv(struct Hsv hsv)
{
    double chroma = hsv.value * hsv.saturation;
    double x = chroma * (1 - fabs(fmod(hsv.hue / 60, 2) - 1));
    double base = hsv.value - chroma;
    double r = 0;
    double g = 0;
    double b = 0;
    int sector = (int)(hsv.hue / 60) % 6;
    switch (sector)
    {
        case 0:
            r = chroma;
            g = x;
            break;
        case 1:
            r = x;
            g = chroma;
            break;
        case 2:
            g = chroma;
            b = x;
            break;
        case 3:
            g = x;
            b = chroma;
            break;
        case 4:
            r = x;
            b = chroma;
            break;
        case 5:
            r = chroma;
            b = x;
            break;
    }
    struct Color color = {(int)lround((r + base) * 255),
        (int)lround((g + base) * 255), (int)lround((b + base) * 255)};
    return clamp_color(color);
}

void color_statistics(const struct Canvas *canvas)
{
    unsigned count = canvas->width * canvas->height;
    double total[3] = {0};
    double square[3] = {0};
    unsigned gray = 0;
    int darkest = 255;
    int lightest = 0;
    for (unsigned i = 0; i < count; i++)
    {
        struct Color color = canvas->pixels[i];
        int light = brightness(color);
        if (light < darkest)
            darkest = light;
        if (light > lightest)
            lightest = light;
        int values[3] = {color.red, color.green, color.blue};
        for (unsigned channel = 0; channel < 3; channel++)
        {
            total[channel] += values[channel];
            square[channel] += values[channel] * values[channel];
        }
        gray += color.red == color.green && color.green == color.blue;
    }
    for (unsigned channel = 0; channel < 3; channel++)
    {
        double mean = total[channel] / count;
        double deviation = sqrt(fmax(0, square[channel] / count - mean * mean));
        printf("channel %u mean %.6f deviation %.6f\n", channel, mean, deviation);
    }
    printf("gray %u colored %u\n", gray, count - gray);
    printf("brightness-range %d %d\n", darkest, lightest);
}

void color_histogram(const struct Canvas *canvas)
{
    unsigned bins[3][16] = {{0}};
    for (unsigned i = 0; i < canvas->width * canvas->height; i++)
    {
        bins[0][canvas->pixels[i].red / 16]++;
        bins[1][canvas->pixels[i].green / 16]++;
        bins[2][canvas->pixels[i].blue / 16]++;
    }
    for (unsigned i = 0; i < 16; i++)
        printf("%u %u %u %u\n", i, bins[0][i], bins[1][i], bins[2][i]);
}
