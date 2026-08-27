ure2D(inputImageTexture, bottomTextureCoordinate).rgb;
                    
                    gl_FragColor = vec4((textureColor * centerMultiplier - (leftTextureColor * edgeMultiplier + rightTextureColor * edgeMultiplier + topTextureColor * edgeMultiplier + bottomTextureColor * edgeMultiplier)), texture2D(inputImageTexture, bottomTextureCoordinate).w);
                }
#endif

#ifdef MEITU_SHARPEN_VERSION_1
    uniform float imageWidthFactor;
    uniform float imageHeightFactor;
    uniform float sharpness;

    varying vec2 v_texCoord;

    vec4 sharpen(vec4 baseColor, float intensity)
    {
        if(intensity == 0.0)
        {
            return baseColor;
        }

        float surfaceWidth  = 1.0 / imageWidthFactor;
        float surfaceHeight = 1.0 / imageHeightFactor;

        vec4 result_color = baseColor;

        float bitmapMaxLength = max(surfaceHeight, surfaceWidth);
        float f = abs(intensity);

        float f2 = (bitmapMaxLength - 1000.0) / 2000.0;
        f2 = max(0.0, min(f2, 1.0));
        f = ((f * 4.0) * (((1.0 - f2) * 0.65) + (f2 * 1.2))) + 1.0;
        float f3 = (1.0 - f) * 0.25;

        vec4 color_left = texture2D(inputImageTexture, v_texCoord+vec2(-1.0/surfaceWidth, 0.0));
        color_left.rgb = color_left.rgb/(color_left.a+0.001);
        vec4 color_right = texture2D(inputImageTexture, v_texCoord+vec2(1.0/surfaceWidth, 0.0));
        color_right.rgb = color_right.rgb/(color_right.a+0.001);
        vec4 color_bottom = texture2D(inputImageTexture, v_texCoord+vec2(0.0, 1.0/surfaceHeight));
        color_bottom.rgb = color_bottom.rgb/(color_bottom.a+0.001);
        vec4 color_top = texture2D(inputImageTexture, v_texCoord+vec2(0.0, -1.0/surfaceHeight));
        color_top.rgb = color_top.rgb/(color_top.a+0.001);
        result_color.rgb = f*result_color.rgb + f3*color_left.rgb + f3*color_right.rgb + f3*color_top.rgb + f3*color_bottom.rgb;
        result_color = clamp(result_color, 0.0, 1.0);
        return result_color;
    }

    void main()
    {
      gl_FragColor = sharpen(texture2D(inputImageTexture, v_texCoord), sharpness);
    }
#endif
                