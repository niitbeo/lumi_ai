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
varying highp vec2 textureCoordinate;                         		        
uniform sampler2D inputImageTexture;                                       
uniform sampler2D inputImageTexture1;                                      
                                                                           
uniform vec4 maxminFlow;                                                   
uniform vec2 texOffset;                                                    
                                                              		        
void main()                                                   		        
{                                                                          
   vec4 flow_pos = texture2D(inputImageTexture1, textureCoordinate);	    
   vec2 pos = (flow_pos.xy * maxminFlow.xy + maxminFlow.zw) * texOffset;   
   gl_FragColor = texture2D(inputImageTexture, textureCoordinate + pos);	
}                                                                          
