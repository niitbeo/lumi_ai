#ifdef GL_ES//for discriminate GLES & GL 
precision mediump float;                 
#else                                    
#define highp                            
#define mediump                          
#define lowp                             
#endif                                   
varying highp vec2 textureCoordinate;          
uniform sampler2D inputImageTexture;           
void main()                                            
{                                                      
   vec2 xy0 = textureCoordinate.xy;                    
   vec4 cc = texture2D(inputImageTexture, xy0);        
   gl_FragColor = vec4(cc.a, cc.a, cc.a, cc.a);        
}                                                      
