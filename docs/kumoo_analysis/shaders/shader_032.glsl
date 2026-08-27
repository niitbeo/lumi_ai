
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
    uniform sampler2D s_texture;

    void main()
    {
        gl_FragColor = vec4(vec3(1.0), texture2D(s_texture,v_texcoord).a);
    }
