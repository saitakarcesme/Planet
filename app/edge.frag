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
};
void main() {
    vec2 p = origin + qt_TexCoord0 * extent;
    vec2 q = abs(p - viewport * 0.5) - (viewport * 0.5 - vec2(15.0));
    float distance = -(length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - 15.0);
    float angle = atan((p.y - viewport.y * 0.5) / viewport.y,
                       (p.x - viewport.x * 0.5) / viewport.x);
    float wave = 0.5 + 0.5 * sin(angle * 3.0 - phase);
    float swell = 0.5 + 0.5 * cos(angle * 2.0 + phase);
    float light = (0.25 + 0.5 * wave) * exp(-max(distance, 0.0) / (2.0 + 3.0 * swell))
                + 0.10 * wave * exp(-max(distance, 0.0) / 13.0);
    float alpha = light * smoothstep(-1.0, 0.5, distance) * qt_Opacity;
    fragColor = vec4(vec3(alpha), alpha);
}
