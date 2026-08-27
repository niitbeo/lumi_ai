varying highp vec2 textureCoordinate;                         		     
uniform sampler2D inputImageTexture;                                    
                                                                        
uniform vec2 texOffset;                                                 
                                                              		     
void main()                                                   		     
{                                                                       
   vec2 tex0 = textureCoordinate - texOffset * 0.5;                    
                                                                        
   gl_FragColor = 0.25 * (texture2D(inputImageTexture, tex0) +          
   texture2D(inputImageTexture, vec2(tex0.x + texOffset.x, tex0.y)) +   
   texture2D(inputImageTexture, vec2(tex0.x, tex0.y + texOffset.y)) +   
   texture2D(inputImageTexture, tex0 + texOffset));			         
}                                                                       
