varying highp vec2 textureCoordinate;                             
varying highp vec2 textureCoordinate2;                             
uniform sampler2D inputImageTexture;                           
uniform sampler2D inputImageTexture1;                          
uniform sampler2D inputImageTexture2;                          
uniform highp vec2 vecParam;                                    
                                                                  
void main()                                                       
{                                                              
   vec2 offset = texture2D(inputImageTexture1, textureCoordinate2).xy;        
   float alpha = texture2D(inputImageTexture2, textureCoordinate2).x;        
   vec2 pos = vec2(textureCoordinate.x - offset.x * vecParam.x * alpha, textureCoordinate.y - offset.y * vecParam.y * alpha);        
   gl_FragColor = texture2D(inputImageTexture, pos);        
}                                                              
