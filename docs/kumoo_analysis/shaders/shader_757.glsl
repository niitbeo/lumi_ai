
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
uniform sampler2D u_texture;
uniform sampler2D stripe32_Texture;// R G B Gray
uniform sampler2D u_maskTexture;

uniform float redAlpha;
uniform float greenAlpha;
uniform float blueAlpha;
uniform float type;

void main(){
    vec4 srcColor = texture2D(u_texture, v_texcoord);
    vec4 dstColor = srcColor;

    dstColor.r = texture2D(stripe32_Texture, vec2(srcColor.r, 0.0)).r;
    dstColor.g = texture2D(stripe32_Texture, vec2(srcColor.g, 0.0)).g;
    dstColor.b = texture2D(stripe32_Texture, vec2(srcColor.b, 0.0)).b;

    //