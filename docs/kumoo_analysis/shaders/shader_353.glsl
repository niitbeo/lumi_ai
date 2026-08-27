
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
        uniform sampler2D destTexture;
        uniform sampler2D tempTexture;
        uniform sampler2D blendTexture;
        uniform float enableBlendAlpha;
        uniform int enableSkipMultiSrc;
        void main()
        {
            vec4 srcColor = texture2D(u_texture, v_texcoord);
            vec4 destColor = texture2D(destTexture, v_texcoord);
            vec4 tempColor = texture2D(tempTexture, v_texcoord);
            vec4 resultColor = vec4(0.0);
            resultColor.r = texture2D(blendTexture, vec2(tempColor.r,srcColor.r)).r;
            resultColor.g = texture2D(blendTexture, vec2(tempColor.g,srcColor.g)).g;
            resultColor.b = texture2D(blendTexture, vec2(tempColor.b,srcColor.b)).b;
            resultColor.a = max(destColor.a,tempColor.a);

            if (enableBlendAlpha == 1.0) {
                resultColor = mix(destColor,resultColor,tempColor.a);
                if (enableSkipMultiSrc == 1) {
                    // nothing...
                } else {
                    resultColor.a = srcColor.a * resultColor.a;
                }
                gl_FragColor = resultColor;
            }
            else {
                resultColor.a = resultColor.a * srcColor.a;
                gl_FragColor = resultColor;
            }
        }
    