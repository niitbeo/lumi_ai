   quad1.y = max(min(4.0,floor(floor(blueColor) * 0.25)),0.0);
           quad1.x = max(min(4.0,floor(blueColor) - (quad1.y * 4.0)),0.0);

           vec2 quad2;
           quad2.y = max(min(floor(ceil(blueColor) * 0.25),4.0),0.0);
           quad2.x = max(min(ceil(blueColor) - (quad2.y * 4.0),4.0),0.0);

           vec2 texPos1;
           texPos1.x = (quad1.x * 0.25) + 0.0078125 + ((0.234375) * textureColor.r);
           texPos1.y = (quad1.y * 0.25) + 0.0078125 + ((0.234375) * textureColor.g);

           vec2 texPos2;
           texPos2.x = (quad2.x * 0.25) + 0.0078125 + ((0.234375) * textureColor.r);
           texPos2.y = (quad2.y * 0.25) + 0.0078125 + ((0.234375) * textureColor.g);

           vec4 newColor1 = texture2D(lutTexture, texPos1);
           vec4 newColor2 = texture2D(lutTexture, texPos2);

           vec4 newColor = mix(newColor1, newColor2, fract(blueColor));
           return newColor;
       }

       vec4 lut3d2(vec4 textureColor)
       {
           float blueColor = textureColor.b * 63.0;

           vec2 quad1;
           quad1.y = min(8.0,max(0.0,floor(floor(blueColor) / 8.0)));
           quad1.x = min(8.0,max(0.0,floor(blueColor) - (quad1.y * 8.0)));

           vec2 quad2;
           quad2.y = floor(ceil(blueColor) / 8.0);
           quad2.x = ceil(blueColor) - (quad2.y * 8.0);

           vec2 texPos1;
           texPos1.x = (quad1.x * 0.125) + 0.5/512.0 + ((0.125 - 1.0/512.0) * textureColor.r);
           texPos1.y = (quad1.y * 0.125) + 0.5/512.0 + ((0.125 - 1.0/512.0) * textureColor.g);

           vec2 texPos2;
           texPos2.x = (quad2.x * 0.125) + 0.5/512.0 + ((0.125 - 1.0/512.0) * textureColor.r);
           texPos2.y = (quad2.y * 0.125) + 0.5/512.0 + ((0.125 - 1.0/512.0) * textureColor.g);

           vec4 newColor1 = texture2D(lutTexture, texPos1);
           vec4 newColor2 = texture2D(lutTexture, texPos2);

           vec4 newColor = mix(newColor1, newColor2, fract(blueColor));
           return newColor;
       }

       void main()
       {
           vec4 orgColor = texture2D(u_texture, v_texcoord);
           if(type > 0.0){
               vec4 tempColor = lut3d2(orgColor);
               gl_FragColor = vec4(mix(orgColor, tempColor, alpha).rgb, orgColor.a);
           }else{
               vec4 tempColor = lut3d(orgColor);
               gl_FragColor = vec4(mix(orgColor, tempColor, alpha).rgb, orgColor.a);
           }
       }
    