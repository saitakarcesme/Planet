#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 extent;
    vec2 cardSize;
    vec2 pointer;
    float radius;
    float reveal;
    float hover;
    float pressure;
    float ready;
    float pixelRatio;
};
layout(binding = 1) uniform sampler2D source;

float roundedBox(vec2 p, vec2 halfSize, float r) {
    vec2 q = abs(p) - halfSize + r;
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
}

vec2 boxNormal(vec2 p, vec2 halfSize, float r) {
    vec2 q = abs(p) - halfSize + r;
    vec2 outside = max(q, 0.0);
    if (dot(outside, outside) > 0.0001)
        return normalize(outside) * sign(p);
    return q.x > q.y ? vec2(sign(p.x), 0.0) : vec2(0.0, sign(p.y));
}

vec3 backdrop(vec2 point, float softness) {
    vec2 uv = clamp(point / extent, vec2(0.001), vec2(0.999));
    vec2 stepSize = softness / extent;
    // A small optical diffusion kernel, not a frosted full-surface blur.
    vec3 c = texture(source, uv).rgb * 0.40;
    c += texture(source, uv + vec2(stepSize.x, 0.0)).rgb * 0.12;
    c += texture(source, uv - vec2(stepSize.x, 0.0)).rgb * 0.12;
    c += texture(source, uv + vec2(0.0, stepSize.y)).rgb * 0.12;
    c += texture(source, uv - vec2(0.0, stepSize.y)).rgb * 0.12;
    c += texture(source, uv + stepSize).rgb * 0.03;
    c += texture(source, uv - stepSize).rgb * 0.03;
    c += texture(source, uv + vec2(stepSize.x, -stepSize.y)).rgb * 0.03;
    c += texture(source, uv + vec2(-stepSize.x, stepSize.y)).rgb * 0.03;
    return c;
}

void main() {
    vec2 pixel = qt_TexCoord0 * extent;
    vec2 p = pixel - extent * 0.5;
    vec2 halfSize = cardSize * 0.5;
    float sd = roundedBox(p, halfSize, radius);
    float aa = max(fwidth(sd), 0.65 / max(pixelRatio, 1.0));
    float coverage = 1.0 - smoothstep(-aa * 0.6, aa * 0.6, sd);
    float shadowDistance = max(roundedBox(p - vec2(0.0, 3.0), halfSize, radius), 0.0);
    float shadow = (0.12 * exp(-shadowDistance * shadowDistance / 480.0)
                  + 0.012 * exp(-shadowDistance * shadowDistance / 28.0))
                  * (1.0 - coverage) * reveal;
    if (sd > 2.0) {
        fragColor = vec4(0.0, 0.0, 0.0, shadow * qt_Opacity);
        return;
    }

    float inset = max(-sd, 0.0);
    vec2 normal2 = boxNormal(p, halfSize, radius);
    float bevel = min(12.0, radius * 0.40);
    float profile = clamp(1.0 - inset / bevel, 0.0, 1.0);
    // A rounded lens cross-section and Snell refraction. Lensing increases
    // continuously during reveal rather than appearing as a painted border.
    float slope = profile / sqrt(max(1.0 - profile * profile, 0.06));
    vec3 normal = normalize(vec3(normal2 * slope * 0.62, 1.0));
    vec3 ray = refract(vec3(0.0, 0.0, -1.0), normal, 1.0 / 1.43);
    vec2 displacement = ray.xy / max(abs(ray.z), 0.15) * (19.0 + pressure * 2.0) * reveal;
    float diffusion = mix(0.55, 1.6, profile) * reveal;
    vec3 seen = backdrop(pixel + displacement, diffusion);
    float luminance = dot(seen, vec3(0.2126, 0.7152, 0.0722));
    // Neutral graphite transmission keeps white text readable on light pages.
    float transmitted = 0.045 + 0.22 * luminance / (0.48 + luminance);
    vec3 body = vec3(transmitted);
    body = mix(vec3(0.085), body, ready);

    vec2 lightPosition = mix(vec2(-0.38, -0.82),
        (pointer / max(cardSize, vec2(1.0)) - 0.5) * 1.5, hover * 0.45);
    vec3 light = normalize(vec3(lightPosition, 0.75));
    vec3 halfVector = normalize(light + vec3(0.0, 0.0, 1.0));
    float specular = pow(max(dot(normal, halfVector), 0.0), 22.0);
    float fresnel = pow(1.0 - normal.z, 3.0);
    float edgeLight = exp(-inset * inset / 1.3) *
        (0.035 + 0.18 * max(dot(normal2, normalize(lightPosition)), 0.0));
    float broadLight = specular * profile * (0.045 + hover * 0.025);
    float innerCaustic = exp(-pow((inset - bevel * 0.65) / 3.4, 2.0)) *
        max(dot(-normal2, normalize(lightPosition)), 0.0) * 0.014;
    float surfaceLight = (edgeLight + broadLight + fresnel * 0.018 + innerCaustic) * reveal;
    float pointerDistance = length((p + halfSize - pointer) / vec2(160.0, 85.0));
    float interactionLight = exp(-pointerDistance * pointerDistance * 2.0) * hover * 0.022;
    body += surfaceLight + interactionLight;

    // Sub-LSB spatial dithering prevents 8-bit gradient bands without visible grain.
    float noise = fract(52.9829189 * fract(dot(floor(pixel * pixelRatio),
                                                vec2(0.06711056, 0.00583715)))) - 0.5;
    body += noise / 255.0;
    float alpha = coverage * reveal;
    fragColor = vec4(body * alpha, alpha + shadow * (1.0 - alpha)) * qt_Opacity;
}
