varying vec2 textureCoordinate; varying vec2 textureCoordinate2; uniform sampler2D faceMaskTexture; uniform sampler2D faceMaskAlphaTexture; uniform highp float blurAlpha; void main() { lowp vec3 faceMask = texture2D(faceMaskTexture, textureCoordinate).rgb; lowp vec3 faceMask2D = texture2D(faceMaskTexture, textureCoordinate2).rgb; lowp float faceMaskAlpha = texture2D(faceMaskAlphaTexture, textureCoordinate2).r; 
#if defined WAKE_SKIN_25D_MIX_RB 
 gl_FragColor = vec4(faceMask.r * faceMaskAlpha, faceMask2D.g * faceMaskAlpha, faceMask.b * faceMaskAlpha, blurAlpha); 
#elif defined WAKE_SKIN_25D_MIX_RGB 
 gl_FragColor = vec4(faceMask.r * faceMaskAlpha, faceMask.g * faceMaskAlpha, faceMask.b * faceMaskAlpha, blurAlpha); 
#elif defined WAKE_SKIN_25D_MIX_RBA 
 lowp float blendAlpha= textureCoordinate.x < 0.5 ? 0.0 : blurAlpha; gl_FragColor = vec4(faceMask.r * faceMaskAlpha, faceMask2D.g * faceMaskAlpha, faceMask.b * faceMaskAlpha, blendAlpha); 
#elif defined WAKE_SKIN_25D_MIX_RGBA 
 lowp float blendAlpha= textureCoordinate.x < 0.5 ? 0.0 : blurAlpha; gl_FragColor = vec4(faceMask.r * faceMaskAlpha, faceMask.g * faceMaskAlpha, faceMask.b * faceMaskAlpha, blendAlpha); 
#else 
 gl_FragColor = vec4(faceMask2D.r * faceMaskAlpha, faceMask.g * faceMaskAlpha, faceMask2D.b * faceMaskAlpha, blurAlpha); 
#endif 
 }