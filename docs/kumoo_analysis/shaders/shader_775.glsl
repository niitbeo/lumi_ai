
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

    uniform sampler2D s_srcTexture;
    uniform sampler2D s_dstTexture;
    uniform sampler2D s_mask;

    uniform highp float alpha;
    uniform highp int maskType;

    void main()
    {
        highp vec4 maskColor = texture2D(s_mask, v_texcoord);
        float protectMaskColor = maskColor.r;
        if (maskType == 1) {
            protectMaskColor = 1.0 - maskColor.r;
        }

        if (protectMaskColor > 0.0) {
            vec4 inputColorSrc = texture2D(s_srcTexture, v_texcoord);
            vec4 inputColorDst = texture2D(s_dstTexture, v_texcoord);
            gl_FragColor = mix(inputColorDst, inputColorSrc, alpha * protectMaskColor);
        } else {
            gl_FragColor = texture2D(s_dstTexture, v_texcoord);
        }
    }
