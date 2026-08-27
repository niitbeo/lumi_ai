
    return fract(sin(dot(uv, vec2(12.9898, 78.233))) * 43758.5453) * smoothIntensity * 0.01;
}
void main() {
    vec4 orgColor = texture2D(u_texture, v_texcoord);
    float srcTexAlpha = orgColor.a;

    vec4 resultColor = orgColor;

    // 