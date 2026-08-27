varying highp vec2 textureCoordinate; varying vec2 textureCoordinateFace; uniform sampler2D inputImageTexture; uniform sampler2D inputImageTexture2; uniform sampler2D skinMaskTexture; uniform sampler2D eyeSokcetsMaskTexture; 
#ifdef MINIFACE_OPT
 uniform sampler2D fullMaskTexture; uniform float miniFaceOpt; 
#endif
 void main() { mediump vec4 srcColor = texture2D(inputImageTexture, textureCoordinate); lowp float mask = texture2D(eyeSokcetsMaskTexture, textureCoordinateFace).b; lowp float skin_mask = texture2D(skinMaskTexture, textureCoordinateFace).r; 
#ifdef MINIFACE_OPT
 lowp float fullMaskColor = texture2D(fullMaskTexture, textureCoordinateFace).a; skin_mask = mix(skin_mask, fullMaskColor, miniFaceOpt); 
#endif
 if(mask > 0.05) { lowp vec4 blurColor = texture2D(inputImageTexture2, textureCoordinate); highp float cDistance = distance(vec3(0.0, 0.0, 0.0), max(blurColor.rgb - srcColor.rgb, 0.0)); cDistance = cDistance * cDistance; cDistance = cDistance / (cDistance + 0.000325); cDistance *= step(0.5, cDistance); lowp float eyesocketTestColor = cDistance*skin_mask; 
#ifdef MINIFACE_OPT
 eyesocketTestColor = mix(cDistance*skin_mask, skin_mask, miniFaceOpt); 
#endif
 gl_FragColor = vec4(vec3(eyesocketTestColor), 1.0); } else { gl_FragColor = vec4(srcColor.rgb, 0.0); gl_FragColor = vec4(vec3(0.0), 1.0); } }