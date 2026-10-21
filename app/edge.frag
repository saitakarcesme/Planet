#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 viewport;
    vec2 origin;
    vec2 extent;
    float phase;
    float energy;
    float pixelRatio;
};
void main() {
    vec2 p = origin + qt_TexCoord0 * extent;
    const float corner = 28.0;
    vec2 q = abs(p - viewport * 0.5) - (viewport * 0.5 - vec2(corner));
    float distance = -(length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - corner);
    float aa = max(fwidth(distance), 0.7 / max(pixelRatio, 1.0));
    float mask = smoothstep(-aa, aa, distance);
    float d = max(distance, 0.0);
    vec2 uv = (p - viewport * 0.5) / viewport;
    float angle = atan(uv.y, uv.x);
    // Several broad, differently paced light fields avoid a rotating rigid ring.
    float field = 0.5 + 0.25 * sin(angle * 2.0 - phase)
                      + 0.15 * sin(angle * 3.0 + phase * 2.0 + 1.7)
                      + 0.10 * cos(angle - phase * 3.0 + 0.8);
    field = smoothstep(0.05, 0.95, field);
    float breadth = 14.0 + 17.0 * field + 6.0 * energy;
    float bloom = (0.035 + 0.13 * field) * exp(-d * d / (breadth * breadth));
    float core = (0.035 + 0.23 * pow(field, 1.8)) *
                 exp(-d * d / (3.8 + 5.5 * field));
    float haze = (0.012 + 0.024 * field) * exp(-d * d / 1450.0);
    // A tiny neutral occlusion keeps white light perceptible over bright pages.
    float shade = 0.025 * exp(-pow((d - 8.0) / 11.0, 2.0));
    float noise = fract(52.9829189 * fract(dot(floor(p * pixelRatio),
                                             vec2(0.06711056, 0.00583715)))) - 0.5;
    float light = max(0.0, bloom + core + haze + noise / 510.0);
    float alpha = (light + shade) * mask * qt_Opacity;
    fragColor = vec4(vec3(light * mask * qt_Opacity), alpha);
}
