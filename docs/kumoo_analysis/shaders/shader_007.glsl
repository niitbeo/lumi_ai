
void main() {
    vec4 bgColor;
    vec4 color = texture2D(u_texture, texcoordOut);
    if(u_colorMode == 0)
    {
        bgColor = color;
    }
    else if(u_colorMode == 1)
    {
        // gl_FragColor = texture2D(u_texture, texcoordOut);
        float row = floor(mod(gl_FragCoord.x, 20.0) / 10.0); // 0 