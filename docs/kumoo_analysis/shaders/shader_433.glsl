
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
uniform sampler2D s_faceMaskTexture;
uniform sampler2D s_resTexture;
uniform float u_alpha;
void main()
{
    vec4 src = texture2D(s_srcTexture,v_srcCoord);
    vec4 faceMask = texture2D(s_faceMaskTexture,v_texCoord);
    vec4 res = texture2D(s_resTexture,v_srcCoord);
    gl_FragColor = mix(src, res, (1.0 - faceMask.r)*u_alpha);
}
