
#ifdef GL_ES
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
#else
#define highp
#define mediump
#define lowp
#endif

varying vec2 v_texcoord;
uniform sampler2D s_srcTexture;
uniform sampler2D s_mask;
uniform vec4 u_blendColor;
uniform vec2 u_src_size;
uniform int drawInstanceColor;

vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

int getLabel(vec4 texColor) {
    int low = int(texColor.r * 255.0);
    int high = int(texColor.g * 255.0);
    return low + high * 256;
}

vec3 getColorFromLabel(int label) {
    float hue = mod(float(label) * 40.0, 360.0);
    return hsv2rgb(vec3(hue / 360.0, 1.0, 1.0));
}

void main()
{
    vec4 colorMask = texture2D(s_mask,v_texcoord);
    vec4 colorSrc = texture2D(s_srcTexture,gl_FragCoord.xy/u_src_size);
    
    vec3 blendMask = u_blendColor.rgb * colorMask.r;
    if (drawInstanceColor == 1) {
        int label = getLabel(colorMask);
        if (label == 0) discard;
        blendMask = getColorFromLabel(label);
    }

    gl_FragColor =  colorSrc + vec4(blendMask,  0);
}
