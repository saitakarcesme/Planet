// Local Wayland pointer transport. Protocol license is in protocols/*.xml.
#include <wayland-client.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "pointer-protocol.h"
static struct zwlr_virtual_pointer_manager_v1 *manager;
static void global(void *data,struct wl_registry *r,uint32_t name,const char *interface,uint32_t version) {
 (void)data; (void)version;
 if (!strcmp(interface,"zwlr_virtual_pointer_manager_v1")) manager=wl_registry_bind(r,name,&zwlr_virtual_pointer_manager_v1_interface,1);
}
static void removed(void *data,struct wl_registry *r,uint32_t name) {(void)data;(void)r;(void)name;}
static uint32_t stamp(void) {struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint32_t)(t.tv_sec*1000+t.tv_nsec/1000000);}
int main(void) {
 struct wl_display *d=wl_display_connect(NULL);
 if (!d) return 2;
 struct wl_registry *r=wl_display_get_registry(d);
 const struct wl_registry_listener listener={global,removed};
 wl_registry_add_listener(r,&listener,NULL);wl_display_roundtrip(d);
 if (!manager) {fprintf(stderr,"Virtual pointer protocol unavailable\n");return 3;}
 struct zwlr_virtual_pointer_v1 *p=zwlr_virtual_pointer_manager_v1_create_virtual_pointer(manager,NULL);
 char line[128],op[16];unsigned x,y,w,h,b,s;int step;
 while (fgets(line,sizeof(line),stdin)) {
  if (sscanf(line,"move %u %u %u %u",&x,&y,&w,&h)==4 && w && h) zwlr_virtual_pointer_v1_motion_absolute(p,stamp(),x,y,w,h);
  else if (sscanf(line,"button %u %u",&b,&s)==2 && b>=272 && b<=274 && s<=1) zwlr_virtual_pointer_v1_button(p,stamp(),b,s);
  else if (sscanf(line,"scroll %d",&step)==1 && step>=-20 && step<=20) {
   zwlr_virtual_pointer_v1_axis_source(p,WL_POINTER_AXIS_SOURCE_WHEEL);
   zwlr_virtual_pointer_v1_axis_discrete(p,stamp(),WL_POINTER_AXIS_VERTICAL_SCROLL,wl_fixed_from_int(step*10),step);
  }
  else if (sscanf(line,"wait %u",&s)==1 && s<=1000) {usleep(s*1000);continue;}
  else if (sscanf(line,"%15s",op)!=1) continue;
  else {fprintf(stderr,"Invalid pointer command\n");return 4;}
  zwlr_virtual_pointer_v1_frame(p);if(wl_display_roundtrip(d)<0) return 5;
 }
 zwlr_virtual_pointer_v1_destroy(p);zwlr_virtual_pointer_manager_v1_destroy(manager);wl_registry_destroy(r);wl_display_flush(d);wl_display_disconnect(d);
 return 0;
}
