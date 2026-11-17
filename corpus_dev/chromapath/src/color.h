#ifndef CHROMAPATH_COLOR_H
#define CHROMAPATH_COLOR_H
#include <stdio.h>

#define PIXELS 1024
#define SIDE 32

struct Color
{
    int red;
    int green;
    int blue;
};

struct Canvas
{
    unsigned width;
    unsigned height;
    struct Color pixels[PIXELS];
};

struct Hsv
{
    double hue;
    double saturation;
    double value;
};

struct Operation
{
    const char *name;
    struct Color (*apply)(struct Color);
};

struct Settings
{
    int quiet;
    int format;
    int report;
    const char *output;
};

int image_error(const char *message);
int int_token(FILE *input, int *value);
int real_token(FILE *input, double *value);
int color_token(FILE *input, struct Color *color);
int read_canvas(FILE *input, struct Canvas *canvas);
void write_canvas(FILE *output, const struct Canvas *canvas, int format);
int load_canvas(const char *path, struct Canvas *canvas);
int save_canvas(const char *path, const struct Canvas *canvas, int format);
int clamp_channel(int value);
struct Color clamp_color(struct Color color);
int color_equal(struct Color left, struct Color right);
int brightness(struct Color color);
struct Hsv to_hsv(struct Color color);
struct Color from_hsv(struct Hsv hsv);
void color_statistics(const struct Canvas *canvas);
void color_histogram(const struct Canvas *canvas);
int simple_filter(struct Canvas *canvas, const char *name);
int convolve(struct Canvas *canvas, int kind);
void color_adjust(struct Canvas *canvas, int mode, double value);
void quantize(struct Canvas *canvas, int levels);
void ordered_dither(struct Canvas *canvas);
void cluster_palette(struct Canvas *canvas, unsigned clusters);
int resize_canvas(struct Canvas *canvas, unsigned width, unsigned height);
int crop_canvas(struct Canvas *canvas, int x, int y, int width, int height);
void turn_canvas(struct Canvas *canvas, int turns);
void mirror_canvas(struct Canvas *canvas, int vertical);
void draw_pixel(struct Canvas *canvas, int x, int y, struct Color color);
void draw_line(struct Canvas *canvas, int x0, int y0, int x1, int y1, struct Color color);
void draw_rectangle(struct Canvas *canvas, int x0, int y0, int x1, int y1, struct Color color, int fill);
void draw_disk(struct Canvas *canvas, int x, int y, int radius, struct Color color, int fill);
void flood_fill(struct Canvas *canvas, int x, int y, struct Color color);
int interpret(FILE *input, struct Canvas *canvas);
#endif
