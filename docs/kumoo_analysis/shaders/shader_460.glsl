varying highp vec2 textureCoordinate;                
uniform sampler2D inputImageTexture;                 
                                                     
void main()                                          
{                                                    
   vec2 tc = abs(textureCoordinate);                 
   tc = 1.0 - abs(tc - 1.0);                         
                                                     
   gl_FragColor = texture2D(inputImageTexture, tc);  
}                                                    
