
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

            varying vec2 v_srcTex;
            varying vec2 v_materialTex;

            uniform sampler2D s_src;
            uniform sampler2D s_material;
            uniform sampler2D s_mask;

            void main()
            {
                vec4 mask_color = texture2D(s_mask, v_srcTex);
                vec4 src_color = texture2D(s_src, v_srcTex);
                vec4 material_color = texture2D(s_material, v_materialTex);

                float r = pow(mask_color.r, 2.5);
                r = mix(r, 1.0, step(0.76, r));
                //r = mix(0.0, r, step(0.1, r));
                gl_FragColor = mix(material_color, src_color, r);
                //gl_FragColor = material_color * (1.0 - r) + src_color * r;
            }
        