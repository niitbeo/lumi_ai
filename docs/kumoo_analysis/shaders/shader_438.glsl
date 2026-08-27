
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
    varying vec2 v_texcoord;
    uniform sampler2D s_dstTexture;
    uniform sampler2D s_maskTexture;
    uniform vec3 u_brushColor;
    uniform int u_mode;
    uniform mediump sampler2D glitterPatternTexture;
    uniform mediump sampler2D glitterPatternTexture2;
    varying highp vec2 vGlitterPatternTexcoord1;
    varying highp vec2 vGlitterPatternTexcoord2;
    varying highp vec2 vGlitterPatternTexcoord3;
    highp float colorLuminance(highp vec3 rgbColor) {
        const highp vec3 kRGBToYPrime = vec3(0.299, 0.587, 0.114);
        return dot(rgbColor, kRGBToYPrime);
    }
    void main()
    {
        vec4 dstColor = texture2D(s_dstTexture, v_texcoord);
        vec4 srcColor = vec4(u_brushColor, texture2D(s_maskTexture, v_texcoord).r);
        vec3 blendedColor = srcColor.a * srcColor.rgb + (1.0 - srcColor.a) * dstColor.a * dstColor.rgb;
        float blendedAlpha = srcColor.a + (1.0 - srcColor.a) * dstColor.a;
        gl_FragColor = vec4(blendedColor / blendedAlpha, blendedAlpha);
        if(u_mode == 1){
            gl_FragColor = dstColor;
            if(texture2D(s_maskTexture,v_texcoord).r > 0.01){
                gl_FragColor = vec4(dstColor.rgb, max(dstColor.a - texture2D(s_maskTexture,v_texcoord).r, 0.0));
            }
            return;
        }
        highp vec4 materialColor = vec4(u_brushColor, texture2D(s_maskTexture,v_texcoord).r);
        // 