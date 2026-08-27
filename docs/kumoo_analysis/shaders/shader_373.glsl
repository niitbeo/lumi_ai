 maskImage.r;
                }
                else if (maskChannel == 1)
                { // MaskChannelType::Alpha
                    maskImageFactor = maskImage.a;
                }

                float blurredAlpha = maskAvgColor.r;
                vec3 blurredFA = srcAvgColor_factor.rgb;
                vec3 blurredF = blurredFA / vec3(blurredAlpha + 1e-5);
                vec3 blurredB1A = srcAvgColor_oneMinusFactor.rgb;
                vec3 blurredB = blurredB1A / vec3(1.0 - blurredAlpha + 1e-5);

                vec3 tmp1 = blurredF * vec3(-maskImageFactor);
                vec3 tmp2 = blurredB * vec3(maskImageFactor - 1.0);
                vec3 tmp3 = srcImage.rgb + tmp1 + tmp2;

                vec3 fore = blurredF + tmp3 * vec3(maskImageFactor);
                vec4 fgDstColor = vec4(fore, maskImageFactor);

                return fgDstColor;
            }

            vec4 mixprocess(vec4 source)
            {
                vec4 back = backColor;
                vec4 dstColor = vec4(0.0);
                if (backMode > 0)
                {
                    vec4 lut = texture2D(lutTexture, v_texcoord);
                    back.r = dstBackColor.r + (backColor.r - dstBackColor.r) * lut.r;
                    back.g = dstBackColor.g + (backColor.g - dstBackColor.g) * lut.r;
                    back.b = dstBackColor.b + (backColor.b - dstBackColor.b) * lut.r;
                }
                back.a = source.a;

                //float factor = mix(0.0, source.a, step(0.1, source.a));
                dstColor.r = source.r * source.a + back.r * (1.0 - source.a);
                dstColor.g = source.g * source.a + back.g * (1.0 - source.a);
                dstColor.b = source.b * source.a + back.b * (1.0 - source.a);
                //dstColor.rgb = mix(back.rgb, source.rgb,  source.a);
                //dstColor.rgb = vec3(source.a, source.a, source.a);
                dstColor.a = source.a;
                return dstColor;
            }

            void main()
            {
                vec4 res = vec4(0.0);
                res = foregroundEstimator(s_texture, maskTexture, v_texcoord, inputKernelSize, inputBlockSize, input_sigma_space, input_sigma_range);
                gl_FragColor = mixprocess(res);
                gl_FragColor = mixprocess(gl_FragColor);
                if(transparentMode == 0){
                    gl_FragColor.a = 1.0;
                }
                //gl_FragColor = texture2D(maskTexture, v_texcoord);
            }
            