
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
uniform sampler2D u_maskTexture;
uniform float imageWidth;
uniform float imageHeight;
uniform float percent;
uniform int   maskType;


    float CalGaussianFilterValue(float sigma, float param)
    {
       return 0.3989 * exp((-param * param * 0.5) / (sigma * sigma)) / sigma;
    }
    float CalSharpenFilterValue(float sigma, float alpha, float param)
    {
       float impluse = 0.0;
       if(abs(param) < 0.00001)
           impluse = 1.0;
       float gaussianValue = CalGaussianFilterValue(sigma, param);
       return (1.0 + alpha) * impluse - alpha * gaussianValue;
    }
    void main()
    {
        int range = 4;
        highp float alpha = 3.0 * percent;
        int samplePointCount = 9;
        highp float sigma = 4.0;
        highp float kernel[9];
        for(int i = 0; i <= range; i++)
        {
            kernel[i] = kernel[samplePointCount - i - 1] = CalSharpenFilterValue(sigma, alpha, float(i - range));
        }
        highp float total = 0.0;
        for(int i = 0; i < samplePointCount; i++)
        {
            total += kernel[i];
        }

        highp vec3 finalCol = vec3(0.0);
        for(int h = -range; h <= range; h++)
        {
            for(int v = -range; v <= range; v++)
            {
                vec2 uv = (gl_FragCoord.xy + vec2(h, v)) / vec2(imageWidth, imageHeight);
                finalCol += (kernel[v + range] * kernel[h + range] * texture2D(u_texture, uv)).rgb;
            }
        }
        vec2 uv2 = (gl_FragCoord.xy) / vec2(imageWidth, imageHeight);

        vec4 originColor = texture2D(u_texture, vec2(uv2.x, uv2.y));
        vec4 maskColor;
        if(maskType == 0) {
            maskColor = vec4(1.0, 1.0, 1.0, 1.0);
        }else {
            maskColor = texture2D(u_maskTexture, vec2(uv2.x, uv2.y));
        }
        gl_FragColor = mix(originColor, vec4(finalCol / (total * total), 1.0), maskColor.r);
    }
