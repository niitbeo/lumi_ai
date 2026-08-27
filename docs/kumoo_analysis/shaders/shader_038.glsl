
#ifdef MEITU_USE_GL_EXT_shader_framebuffer_fetch
#extension GL_EXT_shader_framebuffer_fetch : require
#endif
#ifdef GL_ES//for discriminate GLES & GL
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
varying vec2 v_srcCoord;
varying vec2 v_texCoord;
uniform sampler2D s_srcTexture;
uniform sampler2D s_genMaskTexture;
uniform sampler2D s_resTexture;
uniform float u_alpha;
uniform float u_maskLeft;
uniform float u_maskRight;
uniform float u_maskTop;
uniform float u_maskBottom;
void main()
{
    vec4 src = texture2D(s_srcTexture,v_srcCoord);
    float maskValue = 1.0;
    if(v_texCoord.x >= u_maskLeft && v_texCoord.x <= u_maskRight && v_texCoord.y >= u_maskTop && v_texCoord.y <= u_maskBottom){
        vec2 uv = vec2((v_texCoord.x - u_maskLeft) / (u_maskRight - u_maskLeft), (v_texCoord.y - u_maskTop) / (u_maskBottom - u_maskTop));
        maskValue *= texture2D(s_genMaskTexture,uv).r;
    }
    vec4 res = texture2D(s_resTexture,v_srcCoord);
    gl_FragColor = mix(src, res, maskValue*u_alpha);
}
