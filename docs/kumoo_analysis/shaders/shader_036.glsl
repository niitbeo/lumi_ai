
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
    varying vec4 v_tempPosition;
    uniform sampler2D s_maskTexture;
    uniform float u_brushAlpha;
    void main()
    {
        vec4 maskTex = texture2D(s_maskTexture,v_texcoord);
        gl_FragColor = vec4(maskTex.rgb, u_brushAlpha);
    }
