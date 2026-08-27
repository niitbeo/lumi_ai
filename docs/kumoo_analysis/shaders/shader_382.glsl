
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
    
    varying highp vec2 v_texcoord;

    uniform sampler2D s_maskTexture1;
    uniform sampler2D s_maskTexture2;
    
    void main()
    {
        float maskColor1 = texture2D(s_maskTexture1, v_texcoord).r;
        float maskColor2 = texture2D(s_maskTexture2, v_texcoord).r;

        float mergedMask = max(maskColor1, maskColor2);
        gl_FragColor = vec4(mergedMask, mergedMask, mergedMask, 1.0);
    }
