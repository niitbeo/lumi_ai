
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
                                                    
                                                    varying vec2 v_materialUV;
                                                    uniform sampler2D s_materialMap;
                                                    
                                                    void main()
                                                    {
                                                        gl_FragColor = texture2D(s_materialMap, v_materialUV);
                                                    }
                                                    
                                                    