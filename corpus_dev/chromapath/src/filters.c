#include "color.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

static struct Color invert_color(struct Color color)
{
    color.red = 255 - color.red;
    color.green = 255 - color.green;
    color.blue = 255 - color.blue;
    return color;
}

static struct Color gray_color(struct Color color)
{
    int value = brightness(color);
    color.red = value;
    color.green = value;
    color.blue = value;
    return color;
}

static struct Color sepia_color(struct Color color)
{
    struct Color result;
    result.red = (393 * color.red + 769 * color.green + 189 * color.blue) / 1000;
    result.green = (349 * color.red + 686 * color.green + 168 * color.blue) / 1000;
    result.blue = (272 * color.red + 534 * color.green + 131 * color.blue) / 1000;
    return clamp_color(result);
}

static struct Color cycle_color(struct Color color)
{
    struct Color result = {color.green, color.blue, color.red};
    return result;
}

static struct Color red_color(struct Color color)
{
    color.green = 0;
    color.blue = 0;
    return color;
}

static struct Color green_color(struct Color color)
{
    color.red = 0;
    color.blue = 0;
    return color;
}

static struct Color blue_color(struct Color color)
{
    color.red = 0;
    color.green = 0;
    return color;
}

static struct Color solar_color(struct Color color)
{
    if (color.red > 127)
        color.red = 255 - color.red;
    if (color.green > 127)
        color.green = 255 - color.green;
    if (color.blue > 127)
        color.blue = 255 - color.blue;
    return color;
}

static struct Color chroma_color(struct Color color)
{
    int low = color.red;
    if (color.green < low)
        low = color.green;
    if (color.blue < low)
        low = color.blue;
    color.red -= low;
    color.green -= low;
    color.blue -= low;
    return color;
}

static const struct Operation operations[] =
{
    {"invert", invert_color},
    {"gray", gray_color},
    {"sepia", sepia_color},
    {"cycle", cycle_color},
    {"red", red_color},
    {"green", green_color},
    {"blue", blue_color},
    {"solar", solar_color},
    {"chroma", chroma_color}
};

int simple_filter(struct Canvas *canvas, const char *name)
{
    for (unsigned i = 0; i < sizeof(operations) / sizeof(*operations); i++)
    {
        if (strcmp(name, operations[i].name))
            continue;
        for (unsigned pixel = 0; pixel < canvas->width * canvas->height; pixel++)
            canvas->pixels[pixel] = operations[i].apply(canvas->pixels[pixel]);
        return 1;
    }
    return 0;
}

static struct Color sample(const struct Canvas *canvas, int x, int y)
{
    if (x < 0)
        x = 0;
    if (y < 0)
        y = 0;
    if (x >= (int)canvas->width)
        x = (int)canvas->width - 1;
    if (y >= (int)canvas->height)
        y = (int)canvas->height - 1;
    return canvas->pixels[(unsigned)y * canvas->width + (unsigned)x];
}

int convolve(struct Canvas *canvas, int kind)
{
    static const int kernels[8][9] =
    {
        {1, 1, 1, 1, 1, 1, 1, 1, 1},
        {1, 2, 1, 2, 4, 2, 1, 2, 1},
        {0, -1, 0, -1, 5, -1, 0, -1, 0},
        {-1, 0, 1, -2, 0, 2, -1, 0, 1},
        {-1, -2, -1, 0, 0, 0, 1, 2, 1},
        {0, 1, 0, 1, -4, 1, 0, 1, 0},
        {-2, -1, 0, -1, 1, 1, 0, 1, 2},
        {1, 0, 0, 0, 1, 0, 0, 0, 1}
    };
    if (kind < 0 || kind > 7)
        return image_error("Invalid convolution kernel");
    int divisor = kind == 0 ? 9 : kind == 1 ? 16 : kind == 7 ? 3 : 1;
    int bias = kind == 6 ? 128 : 0;
    struct Canvas result = *canvas;
    for (unsigned y = 0; y < canvas->height; y++)
    {
        for (unsigned x = 0; x < canvas->width; x++)
        {
            struct Color sum = {0, 0, 0};
            for (int dy = -1; dy <= 1; dy++)
            {
                for (int dx = -1; dx <= 1; dx++)
                {
                    int weight = kernels[kind][(dy + 1) * 3 + dx + 1];
                    struct Color color = sample(canvas, (int)x + dx, (int)y + dy);
                    sum.red += color.red * weight;
                    sum.green += color.green * weight;
                    sum.blue += color.blue * weight;
                }
            }
            sum.red = sum.red / divisor + bias;
            sum.green = sum.green / divisor + bias;
            sum.blue = sum.blue / divisor + bias;
            result.pixels[y * canvas->width + x] = clamp_color(sum);
        }
    }
    *canvas = result;
    return 0;
}

void color_adjust(struct Canvas *canvas, int mode, double value)
{
    for (unsigned i = 0; i < canvas->width * canvas->height; i++)
    {
        struct Color color = canvas->pixels[i];
        if (mode <= 2)
        {
            struct Hsv hsv = to_hsv(color);
            if (mode == 0)
            {
                hsv.hue = fmod(hsv.hue + value, 360);
                if (hsv.hue < 0)
                    hsv.hue += 360;
            }
            else if (mode == 1)
                hsv.saturation = fmax(0, fmin(1, hsv.saturation * value));
            else
                hsv.value = fmax(0, fmin(1, hsv.value * value));
            color = from_hsv(hsv);
        }
        else if (mode == 3)
        {
            color.red += (int)value;
            color.green += (int)value;
            color.blue += (int)value;
        }
        else if (mode == 4)
        {
            color.red = (int)lround((color.red - 127.5) * value + 127.5);
            color.green = (int)lround((color.green - 127.5) * value + 127.5);
            color.blue = (int)lround((color.blue - 127.5) * value + 127.5);
        }
        else
        {
            color.red = (int)lround(255 * pow(color.red / 255.0, value));
            color.green = (int)lround(255 * pow(color.green / 255.0, value));
            color.blue = (int)lround(255 * pow(color.blue / 255.0, value));
        }
        canvas->pixels[i] = clamp_color(color);
    }
}

void quantize(struct Canvas *canvas, int levels)
{
    for (unsigned i = 0; i < canvas->width * canvas->height; i++)
    {
        struct Color *color = &canvas->pixels[i];
        color->red = (color->red * (levels - 1) / 255) * 255 / (levels - 1);
        color->green = (color->green * (levels - 1) / 255) * 255 / (levels - 1);
        color->blue = (color->blue * (levels - 1) / 255) * 255 / (levels - 1);
    }
}

void ordered_dither(struct Canvas *canvas)
{
    static const int bayer[16] = {0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5};
    for (unsigned y = 0; y < canvas->height; y++)
    {
        for (unsigned x = 0; x < canvas->width; x++)
        {
            int threshold = bayer[(y % 4) * 4 + x % 4] * 16 + 8;
            struct Color *color = &canvas->pixels[y * canvas->width + x];
            color->red = color->red >= threshold ? 255 : 0;
            color->green = color->green >= threshold ? 255 : 0;
            color->blue = color->blue >= threshold ? 255 : 0;
        }
    }
}

static unsigned nearest(struct Color color, const struct Color *palette, unsigned count)
{
    unsigned best = 0;
    int distance = 1000000;
    for (unsigned i = 0; i < count; i++)
    {
        int r = color.red - palette[i].red;
        int g = color.green - palette[i].green;
        int b = color.blue - palette[i].blue;
        int next = r * r + g * g + b * b;
        if (next < distance)
        {
            distance = next;
            best = i;
        }
    }
    return best;
}

void cluster_palette(struct Canvas *canvas, unsigned clusters)
{
    struct Color palette[16];
    unsigned count = canvas->width * canvas->height;
    for (unsigned i = 0; i < clusters; i++)
        palette[i] = canvas->pixels[i * count / clusters];
    for (unsigned iteration = 0; iteration < 8; iteration++)
    {
        struct Color sums[16] = {{0, 0, 0}};
        unsigned counts[16] = {0};
        for (unsigned i = 0; i < count; i++)
        {
            unsigned group = nearest(canvas->pixels[i], palette, clusters);
            sums[group].red += canvas->pixels[i].red;
            sums[group].green += canvas->pixels[i].green;
            sums[group].blue += canvas->pixels[i].blue;
            counts[group]++;
        }
        for (unsigned i = 0; i < clusters; i++)
        {
            if (!counts[i])
                continue;
            palette[i].red = sums[i].red / (int)counts[i];
            palette[i].green = sums[i].green / (int)counts[i];
            palette[i].blue = sums[i].blue / (int)counts[i];
        }
    }
    for (unsigned i = 0; i < count; i++)
        canvas->pixels[i] = palette[nearest(canvas->pixels[i], palette, clusters)];
}

int resize_canvas(struct Canvas *canvas, unsigned width, unsigned height)
{
    if (width < 1 || width > SIDE || height < 1 || height > SIDE)
        return image_error("Invalid resize dimensions");
    struct Canvas result = {width, height, {{0, 0, 0}}};
    for (unsigned y = 0; y < height; y++)
    {
        for (unsigned x = 0; x < width; x++)
        {
            unsigned source_x = x * canvas->width / width;
            unsigned source_y = y * canvas->height / height;
            result.pixels[y * width + x] = canvas->pixels[source_y * canvas->width + source_x];
        }
    }
    *canvas = result;
    return 0;
}

int crop_canvas(struct Canvas *canvas, int x, int y, int width, int height)
{
    if (x < 0 || y < 0 || width < 1 || height < 1 ||
        x + width > (int)canvas->width || y + height > (int)canvas->height)
        return image_error("Invalid crop bounds");
    struct Canvas result = {(unsigned)width, (unsigned)height, {{0, 0, 0}}};
    for (int row = 0; row < height; row++)
    {
        for (int column = 0; column < width; column++)
            result.pixels[row * width + column] = canvas->pixels[(y + row) * (int)canvas->width + x + column];
    }
    *canvas = result;
    return 0;
}

void turn_canvas(struct Canvas *canvas, int turns)
{
    turns = (turns % 4 + 4) % 4;
    while (turns--)
    {
        struct Canvas result = {canvas->height, canvas->width, {{0, 0, 0}}};
        for (unsigned y = 0; y < canvas->height; y++)
        {
            for (unsigned x = 0; x < canvas->width; x++)
                result.pixels[x * result.width + canvas->height - y - 1] = canvas->pixels[y * canvas->width + x];
        }
        *canvas = result;
    }
}

void mirror_canvas(struct Canvas *canvas, int vertical)
{
    struct Canvas result = *canvas;
    for (unsigned y = 0; y < canvas->height; y++)
    {
        for (unsigned x = 0; x < canvas->width; x++)
        {
            unsigned sx = vertical ? x : canvas->width - x - 1;
            unsigned sy = vertical ? canvas->height - y - 1 : y;
            result.pixels[y * canvas->width + x] = canvas->pixels[sy * canvas->width + sx];
        }
    }
    *canvas = result;
}

void draw_pixel(struct Canvas *canvas, int x, int y, struct Color color)
{
    if (x < 0 || y < 0 || x >= (int)canvas->width || y >= (int)canvas->height)
        return;
    canvas->pixels[(unsigned)y * canvas->width + (unsigned)x] = color;
}

void draw_line(struct Canvas *canvas, int x0, int y0, int x1, int y1, struct Color color)
{
    int dx = abs(x1 - x0);
    int dy = -abs(y1 - y0);
    int sx = x0 < x1 ? 1 : -1;
    int sy = y0 < y1 ? 1 : -1;
    int error = dx + dy;
    for (;;)
    {
        draw_pixel(canvas, x0, y0, color);
        if (x0 == x1 && y0 == y1)
            break;
        int twice = 2 * error;
        if (twice >= dy)
        {
            error += dy;
            x0 += sx;
        }
        if (twice <= dx)
        {
            error += dx;
            y0 += sy;
        }
    }
}

void draw_rectangle(struct Canvas *canvas, int x0, int y0, int x1, int y1, struct Color color, int fill)
{
    if (x0 > x1)
    {
        int saved = x0;
        x0 = x1;
        x1 = saved;
    }
    if (y0 > y1)
    {
        int saved = y0;
        y0 = y1;
        y1 = saved;
    }
    for (int y = y0; y <= y1; y++)
    {
        for (int x = x0; x <= x1; x++)
        {
            if (fill || x == x0 || x == x1 || y == y0 || y == y1)
                draw_pixel(canvas, x, y, color);
        }
    }
}

void draw_disk(struct Canvas *canvas, int x, int y, int radius, struct Color color, int fill)
{
    for (int dy = -radius; dy <= radius; dy++)
    {
        for (int dx = -radius; dx <= radius; dx++)
        {
            int distance = dx * dx + dy * dy;
            if (distance > radius * radius)
                continue;
            if (fill || radius == 0 || distance >= (radius - 1) * (radius - 1))
                draw_pixel(canvas, x + dx, y + dy, color);
        }
    }
}

void flood_fill(struct Canvas *canvas, int x, int y, struct Color color)
{
    if (x < 0 || y < 0 || x >= (int)canvas->width || y >= (int)canvas->height)
        return;
    struct Color original = canvas->pixels[(unsigned)y * canvas->width + (unsigned)x];
    if (color_equal(original, color))
        return;
    unsigned queue[PIXELS];
    unsigned first = 0;
    unsigned end = 0;
    unsigned index = (unsigned)y * canvas->width + (unsigned)x;
    queue[end++] = index;
    canvas->pixels[index] = color;
    while (first < end)
    {
        index = queue[first++];
        unsigned px = index % canvas->width;
        unsigned py = index / canvas->width;
        unsigned neighbors[4];
        unsigned count = 0;
        if (px)
            neighbors[count++] = index - 1;
        if (py)
            neighbors[count++] = index - canvas->width;
        if (px + 1 < canvas->width)
            neighbors[count++] = index + 1;
        if (py + 1 < canvas->height)
            neighbors[count++] = index + canvas->width;
        for (unsigned i = 0; i < count; i++)
        {
            unsigned next = neighbors[i];
            if (!color_equal(canvas->pixels[next], original))
                continue;
            canvas->pixels[next] = color;
            queue[end++] = next;
        }
    }
}
