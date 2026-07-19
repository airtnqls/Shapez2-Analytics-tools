#include <algorithm>
#include <array>
#include <bit>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <functional>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <set>
#include <span>
#include <string>
#include <tuple>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace half_oracle {

enum Cell : uint8_t { E=0, N=1, P=2, C=3 };

struct Engine {
  int L;
  int NC=4;
  uint64_t cell_mask;
  uint64_t pos_mask;
  uint64_t bot_mask;
  uint64_t top_mask;
  uint64_t east_pos;

  explicit Engine(int layers):L(layers) {
    if (L<1 || L>7) throw std::runtime_error("L must be 1..7");
    const int cells=4*L;
    cell_mask = cells==32 ? ~uint64_t(0) : ((uint64_t(1)<<(2*cells))-1);
    pos_mask = cells==64 ? ~uint64_t(0) : ((uint64_t(1)<<cells)-1);
    bot_mask=0; top_mask=0; east_pos=0;
    for(int q=0;q<4;q++){bot_mask|=uint64_t(1)<<q;top_mask|=uint64_t(1)<<((L-1)*4+q);}    
    for(int l=0;l<L;l++) for(int q=0;q<2;q++) east_pos|=uint64_t(1)<<(l*4+q);
  }

  inline int idx(int l,int q) const {return l*4+q;}
  inline Cell at(uint64_t s,int l,int q) const {
    if(l<0||l>=L) return E;
    return Cell((s>>(2*idx(l,q)))&3u);
  }
  inline uint64_t set(uint64_t s,int l,int q,Cell v) const {
    uint64_t sh=2*idx(l,q);return (s&~(uint64_t(3)<<sh))|(uint64_t(v)<<sh);
  }
  uint64_t occ(uint64_t s) const {uint64_t m=0;for(int i=0;i<4*L;i++)if(((s>>(2*i))&3)!=0)m|=uint64_t(1)<<i;return m;}
  uint64_t type_mask(uint64_t s,Cell t) const {uint64_t m=0;for(int i=0;i<4*L;i++)if(((s>>(2*i))&3)==t)m|=uint64_t(1)<<i;return m;}
  uint64_t crystals(uint64_t s) const {return type_mask(s,C);}  
  uint64_t normals(uint64_t s) const {return type_mask(s,N);}  
  uint64_t nonpins(uint64_t s) const {return type_mask(s,N)|type_mask(s,C);}  
  uint64_t expand_positions(uint64_t p) const {uint64_t m=0;while(p){int i=std::countr_zero(p);p&=p-1;m|=uint64_t(3)<<(2*i);}return m;}
  uint64_t remove_positions(uint64_t s,uint64_t p) const {return s & ~expand_positions(p);}  

  uint64_t shift_pos_up(uint64_t p) const {return (p<<4)&pos_mask;}
  uint64_t shift_pos_down(uint64_t p) const {return p>>4;}
  uint64_t shift_shape_up(uint64_t s) const {return (s<<8)&cell_mask;}
  uint64_t shift_shape_down_subset(uint64_t content) const {return content>>8;}

  uint64_t rotate_pos_cw(uint64_t p) const {uint64_t out=0;for(int l=0;l<L;l++)for(int q=0;q<4;q++)if(p&(uint64_t(1)<<idx(l,q)))out|=uint64_t(1)<<idx(l,(q+1)&3);return out;}
  uint64_t rotate_pos_ccw(uint64_t p) const {uint64_t out=0;for(int l=0;l<L;l++)for(int q=0;q<4;q++)if(p&(uint64_t(1)<<idx(l,q)))out|=uint64_t(1)<<idx(l,(q+3)&3);return out;}
  uint64_t rotate_cw(uint64_t s) const {uint64_t out=0;for(int l=0;l<L;l++)for(int q=0;q<4;q++)out=set(out,l,(q+1)&3,at(s,l,q));return out;}
  uint64_t rotate_180(uint64_t s) const {return rotate_cw(rotate_cw(s));}
  uint64_t mirror(uint64_t s) const {uint64_t out=0;static int mp[4]={3,2,1,0};for(int l=0;l<L;l++)for(int q=0;q<4;q++)out=set(out,l,mp[q],at(s,l,q));return out;}
  uint64_t half_sym(uint64_t h) const {return rotate_180(mirror(h));}

  uint32_t compact_half(uint64_t h) const {uint32_t k=0;for(int l=0;l<L;l++)for(int q=0;q<2;q++)k|=uint32_t(at(h,l,q))<<(2*(l*2+q));return k;}
  uint64_t expand_half(uint32_t k) const {uint64_t h=0;for(int l=0;l<L;l++)for(int q=0;q<2;q++)h=set(h,l,q,Cell((k>>(2*(l*2+q)))&3));return h;}
  uint32_t half_sym_key(uint32_t k) const {uint32_t o=0;for(int l=0;l<L;l++){uint32_t a=(k>>(4*l))&3,b=(k>>(4*l+2))&3;o|=b<<(4*l);o|=a<<(4*l+2);}return o;}
  uint32_t canon_key(uint32_t k) const {return std::min(k,half_sym_key(k));}
  uint32_t canon_half(uint64_t h) const {return canon_key(compact_half(h));}

  int height_col(uint64_t s,int q) const {for(int l=L-1;l>=0;l--)if(at(s,l,q)!=E)return l+1;return 0;}
  int num_layers(uint64_t s) const {int h=0;for(int q=0;q<4;q++)h=std::max(h,height_col(s,q));return h;}
  bool empty(uint64_t s) const {return s==0;}

  uint64_t spread_horizontal(uint64_t m,uint64_t filter,bool cutmode) const {
    uint64_t out=0;
    for(int l=0;l<L;l++)for(int q=0;q<4;q++) if(m&(uint64_t(1)<<idx(l,q))){
      int a=(q+1)&3,b=(q+3)&3;
      auto allowed=[&](int x,int y){ if(!cutmode)return true; return (x<2)==(y<2);};
      if(allowed(q,a) && (filter&(uint64_t(1)<<idx(l,a)))) out|=uint64_t(1)<<idx(l,a);
      if(allowed(q,b) && (filter&(uint64_t(1)<<idx(l,b)))) out|=uint64_t(1)<<idx(l,b);
    }
    return out;
  }

  uint64_t shatter(uint64_t s,uint64_t seeds,bool cutmode=false) const {
    uint64_t cr=crystals(s), sh=seeds&cr;
    if(!sh)return s;
    while(true){uint64_t prev=sh;sh|=spread_horizontal(sh,cr,cutmode);sh|=shift_pos_up(sh)&cr;sh|=shift_pos_down(sh)&cr;if(sh==prev)break;}
    return remove_positions(s,sh);
  }

  uint64_t gravity(uint64_t shape,bool cutmode=false) const {
    if(!shape)return 0;
    uint64_t occupied=occ(shape), crystal=crystals(shape), nonpin=nonpins(shape);
    uint64_t supported=occupied&bot_mask;
    // full fixed point, small width/runtime cap.
    while(true){
      uint64_t prev=supported;
      supported |= shift_pos_up(supported)&occupied;
      supported |= spread_horizontal(supported&nonpin,nonpin,cutmode);
      supported |= shift_pos_down(supported&crystal)&crystal;
      if(supported==prev)break;
    }
    if(supported==occupied)return shape;
    shape=remove_positions(shape,crystal&~supported);
    uint64_t unsupported=(occupied&~supported)&~crystal;
    unsupported &= pos_mask;
    if(!unsupported)return shape;
    uint64_t falling_nonpin=unsupported&nonpin;
    while(unsupported){
      uint64_t content=shape&expand_positions(unsupported);
      shape=remove_positions(shape,unsupported)|shift_shape_down_subset(content);
      unsupported=shift_pos_down(unsupported);
      falling_nonpin=shift_pos_down(falling_nonpin);
      uint64_t settled=(unsupported&bot_mask)|(unsupported&shift_pos_up(supported));
      while(true){uint64_t prev=settled;settled|=shift_pos_up(settled)&unsupported;settled|=spread_horizontal(settled&falling_nonpin,falling_nonpin,cutmode);if(settled==prev)break;}
      supported|=settled;unsupported&=~settled;falling_nonpin&=~settled;
    }
    return shape;
  }

  std::pair<uint64_t,uint64_t> cut(uint64_t shape) const {
    uint64_t cr=crystals(shape),seeds=0;
    for(int l=0;l<L;l++){
      if(at(shape,l,1)==C&&at(shape,l,2)==C){seeds|=uint64_t(1)<<idx(l,1);seeds|=uint64_t(1)<<idx(l,2);}      
      if(at(shape,l,3)==C&&at(shape,l,0)==C){seeds|=uint64_t(1)<<idx(l,3);seeds|=uint64_t(1)<<idx(l,0);}      
    }
    (void)cr;
    shape=shatter(shape,seeds,true);shape=gravity(shape,true);
    uint64_t east=0,west=0;for(int l=0;l<L;l++)for(int q=0;q<4;q++)if(q<2)east=set(east,l,q,at(shape,l,q));else west=set(west,l,q,at(shape,l,q));
    return {east,west};
  }

  uint64_t pin_push(uint64_t shape) const {
    if(!shape)return shape;
    uint64_t old_top=crystals(shape)&top_mask;
    uint64_t result=shift_shape_up(shape);
    for(int q=0;q<4;q++)if(at(shape,0,q)!=E)result=set(result,0,q,P);
    if(shape&expand_positions(top_mask)) result=shatter(result,old_top,false);
    return gravity(result,false);
  }

  uint64_t stack_layer(uint64_t bottom,const std::array<Cell,4>& piece) const {
    int land=0;for(int q=0;q<4;q++)if(piece[q]!=E)land=std::max(land,height_col(bottom,q));
    if(land>=L)return bottom;
    for(int q=0;q<4;q++)if(piece[q]!=E)bottom=set(bottom,land,q,piece[q]);
    return bottom;
  }

  uint64_t support_crystals(uint64_t seeds) const {
    uint64_t s=0;for(int l=0;l<L;l++)for(int q=0;q<4;q++)if(seeds&(uint64_t(1)<<idx(l,q))){for(int k=0;k<l;k++)if(at(s,k,q)==E)s=set(s,k,q,N);s=set(s,l,q,C);}return s;
  }

  std::string code_half(uint32_t k) const {std::string out;for(int l=0;l<L;l++){char row[2];for(int q=0;q<2;q++){static const char *cs="-SPc";row[q]=cs[(k>>(2*(l*2+q)))&3];}if(l)out+=':';out.append(row,2);}while(out.size()>=3&&out.substr(out.size()-3)==":--")out.resize(out.size()-3);if(out=="--")out.clear();return out;}
};

struct Projection {
  uint32_t content=0; // one-column cell sequence in low two bits per layer
  uint32_t inner=0;   // layer mask
  bool operator==(const Projection&o)const{return content==o.content&&inner==o.inner;}
  bool operator<(const Projection&o)const{return std::tie(content,inner)<std::tie(o.content,o.inner);}
};
struct ProjectionHash {size_t operator()(const Projection&p)const{return size_t(p.content)*0x9e3779b1u^p.inner;}};

struct StackProj {
  Projection p;
  uint8_t h0=0,h1=0;
  uint32_t source=0;
};

struct Search {
  Engine e;
  std::unordered_set<uint32_t> seen;
  std::vector<uint32_t> keys;
  size_t queue_head=0;
  std::vector<uint32_t> crystal_column;
  size_t op5_west_cursor=0,op5_east_cursor=0;
  std::vector<Projection> projections;
  std::unordered_set<Projection,ProjectionHash> projection_seen;
  size_t projection_old=0;

  explicit Search(int L):e(L){seen.reserve(1u<<std::min(24,4*L));}
  bool try_add(uint64_t h){uint32_t k=e.canon_half(h);auto [it,ok]=seen.insert(k);if(ok)keys.push_back(k);return ok;}
  bool contains_half(uint64_t h)const{return seen.count(e.canon_half(h));}

  void seeds(){
    for(int h0=0;h0<=e.L;h0++)for(int h1=0;h1<=e.L;h1++){
      int n=h0+h1;uint64_t lim=uint64_t(1)<<n;
      for(uint64_t mask=0;mask<lim;mask++){
        uint64_t s=0;int b=0;for(int q=0;q<2;q++){int h=q?h1:h0;for(int l=0;l<h;l++)s=e.set(s,l,q,(mask&(uint64_t(1)<<b++))?C:N);}try_add(s);
      }
    }
  }

  void op1(uint64_t h){try_add(e.pin_push(h));}
  void op2(uint64_t h){
    static const std::array<std::array<Cell,4>,5> ps={{{N,E,E,E},{E,N,E,E},{N,N,E,E},{P,E,E,E},{E,P,E,E}}};
    for(auto&p:ps)try_add(e.stack_layer(h,p));
  }
  void op3(uint64_t h){
    uint64_t cr=e.crystals(h)&e.east_pos;std::vector<int> pos;while(cr){int i=std::countr_zero(cr);cr&=cr-1;pos.push_back(i);}int n=pos.size();
    for(uint32_t sub=1;sub<(uint32_t(1)<<n);sub++){uint64_t seed=0;for(int i=0;i<n;i++)if(sub&(1u<<i))seed|=uint64_t(1)<<pos[i];uint64_t r=e.gravity(e.shatter(h,seed,true),true);if(r!=h)try_add(r);}
  }

  Projection project(uint64_t half) const {
    Projection p;uint64_t proj=0;for(int l=0;l<e.L;l++)proj=e.set(proj,l,0,e.at(half,l,0));
    uint64_t fire=0;for(int l=0;l<e.L;l++)if(e.at(half,l,0)==C&&e.at(half,l,1)==C)fire|=uint64_t(1)<<e.idx(l,0);
    if(fire){uint64_t before=e.crystals(proj);uint64_t aftershape=e.shatter(proj,fire,false);uint64_t shattered=before&~e.crystals(aftershape);for(int l=0;l<e.L;l++)if(shattered&(uint64_t(1)<<e.idx(l,0)))p.inner|=1u<<l;proj=aftershape;}
    for(int l=0;l<e.L;l++)p.content|=uint32_t(e.at(proj,l,0))<<(2*l);
    return p;
  }
  uint64_t projection_content(const Projection&p,int q)const{uint64_t s=0;for(int l=0;l<e.L;l++)s=e.set(s,l,q,Cell((p.content>>(2*l))&3));return s;}
  uint64_t combine(const Projection&q,const Projection&p)const{
    uint64_t s=projection_content(q,0)|projection_content(p,1),seed=0;
    for(int l=0;l<e.L;l++){if(q.inner&(1u<<l))seed|=uint64_t(1)<<e.idx(l,1);if(p.inner&(1u<<l))seed|=uint64_t(1)<<e.idx(l,0);}return e.shatter(s,seed,false);
  }

  void add_new_projections(){
    for(size_t i=projection_old;i<keys.size();i++){
      uint64_t h=e.expand_half(keys[i]);
      for(int k=0;k<2;k++){Projection p=project(h);if(projection_seen.insert(p).second)projections.push_back(p);h=e.half_sym(h);}    
    }
  }
  void op4_phase(){
    size_t oldp=projections.size();
    // Need source cursor separate from projection count: rebuild from all keys safely.
    size_t before=projections.size();
    for(uint32_t k:keys){uint64_t h=e.expand_half(k);for(int z=0;z<2;z++){Projection p=project(h);if(projection_seen.insert(p).second)projections.push_back(p);h=e.half_sym(h);}}
    size_t new_start=before;
    if(new_start==projections.size())return;
    for(size_t i=new_start;i<projections.size();i++)for(size_t j=0;j<projections.size();j++)try_add(e.gravity(combine(projections[i],projections[j]),false));
    for(size_t i=0;i<new_start;i++)for(size_t j=new_start;j<projections.size();j++)try_add(e.gravity(combine(projections[i],projections[j]),false));
    (void)oldp;
  }

  bool qualifies(uint64_t h)const{
    int nl=e.num_layers(h);if(nl<2)return false;
    for(int l=0;l<nl;l++)if(e.at(h,l,0)!=C)return false;
    if(e.at(h,nl-1,1)!=E)return false;
    int h1=e.height_col(h,1);if(!h1)return false;bool pin=false;
    for(int l=0;l<h1;l++){Cell x=e.at(h,l,1);if(x==C)return false;if(x==P)pin=true;}if(!pin||e.at(h,h1-1,1)==P)return false;return true;
  }
  void record_qual(uint32_t k,uint64_t h){if(qualifies(h))crystal_column.push_back(k);}
  void op5_phase(){
    size_t east_end=keys.size(),west_end=crystal_column.size();
    auto process=[&](size_t wi0,size_t wi1,size_t ei0,size_t ei1){for(size_t wi=wi0;wi<wi1;wi++){uint64_t west=e.expand_half(crystal_column[wi]);uint64_t placed=e.rotate_180(west);for(size_t ei=ei0;ei<ei1;ei++){uint64_t east=e.expand_half(keys[ei]);bool topempty=true;for(int q=0;q<2;q++)if(e.at(east,e.L-1,q)!=E)topempty=false;if(!topempty)continue;bool all=true;for(int q=0;q<2;q++){bool any=false;for(int l=0;l<e.L;l++)if(e.at(east,l,q)==C)any=true;if(!any)all=false;}if(!all)continue;uint64_t r=e.pin_push(east|placed);for(int rot=0;rot<4;rot++){auto [a,b]=e.cut(r);try_add(a);try_add(e.rotate_180(b));r=e.rotate_cw(r);}}}};
    process(op5_west_cursor,west_end,0,east_end);process(0,op5_west_cursor,op5_east_cursor,east_end);op5_west_cursor=west_end;op5_east_cursor=east_end;
  }

  bool valid_arcs(uint32_t normal,uint32_t anchor)const{
    if(!normal)return true;if(normal==15)return normal&anchor;int gap=0;while(normal&(1u<<gap))gap++;for(int i=0;i<4;){int pos=(gap+i)&3;if(!(normal&(1u<<pos))){i++;continue;}uint32_t arc=0;while(i<4&&(normal&(1u<<((gap+i)&3)))){arc|=1u<<((gap+i)&3);i++;}if(!(arc&anchor))return false;}return true;
  }
  std::vector<std::array<Cell,4>> half_layer_entries(uint64_t state,int layer)const{
    uint32_t sup=0,blk=0;for(int c=0;c<2;c++){int h=e.height_col(state,c);if(h>=layer)sup|=1u<<c;if(h>layer)blk|=1u<<c;}for(int c=2;c<4;c++)if(e.height_col(state,c)>layer)blk|=1u<<c;
    uint32_t enum_blk=blk&3;if(enum_blk&~sup)return{};uint32_t enum_anchor=sup&~enum_blk,free=(~enum_blk)&3;
    uint32_t west_anchor=0;std::array<Cell,4> base{E,E,E,E};for(int c=2;c<4;c++)if(!(blk&(1u<<c))){west_anchor|=1u<<c;base[c]=N;}
    uint32_t full_anchor=enum_anchor|west_anchor;std::vector<std::array<Cell,4>> out;
    for(int s=0;s<9;s++){int tmp=s;auto p=base;uint32_t normal=west_anchor;bool ok=true;for(int c=0;c<2;c++,tmp/=3){int v=tmp%3;if(!v)continue;if(!(free&(1u<<c))){ok=false;break;}if(v==2&&!(enum_anchor&(1u<<c))){ok=false;break;}p[c]=Cell(v);if(v==1)normal|=1u<<c;}if(ok&&valid_arcs(normal,full_anchor))out.push_back(p);}return out;
  }

  bool stacking_reconstruction(uint64_t shape,uint64_t prefixmask)const{
    uint64_t stacked=e.pos_mask&~prefixmask;uint64_t normals=e.normals(shape)&stacked;uint64_t anchored=(e.shift_pos_up(e.occ(shape))|e.bot_mask)&stacked;for(int l=0;l<e.L;l++){uint32_t n=0,a=0;for(int q=0;q<4;q++){if(normals&(uint64_t(1)<<e.idx(l,q)))n|=1u<<q;if(anchored&(uint64_t(1)<<e.idx(l,q)))a|=1u<<q;}if(!valid_arcs(n,a))return false;}return true;
  }
  bool is_half_stackable(uint64_t shape)const{
    std::vector<int> sp[2];for(int c=0;c<2;c++){sp[c].push_back(0);int h=e.height_col(shape,c);for(int l=0;l<h;l++){Cell x=e.at(shape,l,c);if(x==C)sp[c].clear();if(x!=E)sp[c].push_back(l+1);}}
    for(int h0:sp[0])for(int h1:sp[1]){uint64_t pm=0;for(int l=0;l<h0;l++)pm|=uint64_t(1)<<e.idx(l,0);for(int l=0;l<h1;l++)pm|=uint64_t(1)<<e.idx(l,1);uint64_t base=shape&e.expand_positions(pm);if(base==shape)continue;if(!stacking_reconstruction(shape,pm))continue;if(contains_half(base))return true;}return false;
  }

  std::vector<uint32_t> base_keys()const{std::vector<uint32_t>b;for(uint32_t k:keys){uint64_t h=e.expand_half(k);if(!is_half_stackable(h))b.push_back(k);}return b;}

  void enumerate_stacking(uint64_t base,uint64_t tops,const std::function<void(uint64_t,uint64_t)>&cb,bool cut_output){
    std::unordered_set<uint64_t> visited;
    std::function<void(uint64_t,int)> dfs=[&](uint64_t stacked,int layer){uint64_t sig=stacked^(uint64_t(layer)<<60);if(!visited.insert(sig).second)return;uint64_t out;
      if(cut_output){out=e.gravity((base|stacked)&e.expand_positions(e.east_pos),true);}else{auto [east,west]=e.cut(base|stacked);(void)west;out=east;}
      cb(out,stacked);if(layer>=e.L)return;uint64_t state=tops|stacked;for(auto &piece:half_layer_entries(state,layer)){uint64_t ns=stacked;for(int q=0;q<4;q++)if(piece[q]!=E)ns=e.set(ns,layer,q,piece[q]);dfs(ns,layer+1);} };
    dfs(0,0);
  }

  Projection stack_projection(uint64_t h)const{return project(h);}  
  std::vector<StackProj> stack_proj_set(const std::vector<uint32_t>&bases)const{
    // Unique tuple (projection,h0,h1), then Pareto for same (projection,h0): keep minimum h1.
    std::map<std::tuple<uint32_t,uint32_t,uint8_t>,StackProj> best;
    for(uint32_t k:bases){uint64_t h=e.expand_half(k);for(int z=0;z<2;z++){StackProj v{project(h),uint8_t(e.height_col(h,0)),uint8_t(e.height_col(h,1)),k};auto key=std::make_tuple(v.p.content,v.p.inner,v.h0);auto it=best.find(key);if(it==best.end()||v.h1<it->second.h1||(v.h1==it->second.h1&&v.source<it->second.source))best[key]=v;h=e.half_sym(h);}}
    std::vector<StackProj> out;for(auto &[k,v]:best)out.push_back(v);return out;
  }

  size_t op6(){size_t before=keys.size();auto bases=base_keys();std::cerr<<"  op6 bases="<<bases.size()<<"\n";
    // no rotation
    for(size_t bi=0;bi<bases.size();bi++){uint32_t k=bases[bi];uint64_t east=e.expand_half(k);uint64_t boundary=e.crystals(east)&e.east_pos;std::vector<int>pos;while(boundary){int i=std::countr_zero(boundary);boundary&=boundary-1;pos.push_back(i);}uint64_t lim=uint64_t(1)<<pos.size();for(uint64_t sub=0;sub<lim;sub++){uint64_t seeds=0;for(size_t i=0;i<pos.size();i++)if(sub&(uint64_t(1)<<i))seeds|=uint64_t(1)<<pos[i];uint64_t mirrored=e.rotate_pos_cw(e.rotate_pos_cw(e.rotate_pos_cw(seeds))); // mirror q0->q3,q1->q2, same as explicit below
        mirrored=0;for(int l=0;l<e.L;l++){if(seeds&(uint64_t(1)<<e.idx(l,0)))mirrored|=uint64_t(1)<<e.idx(l,3);if(seeds&(uint64_t(1)<<e.idx(l,1)))mirrored|=uint64_t(1)<<e.idx(l,2);}uint64_t west=e.support_crystals(mirrored);uint64_t base=east|west;enumerate_stacking(base,base,[&](uint64_t out,uint64_t){if(out)try_add(out);},false);}if((bi+1)%100==0)std::cerr<<"    base "<<bi+1<<"/"<<bases.size()<<" keys="<<keys.size()<<"\n";}
    // rotation path
    auto projs=stack_proj_set(bases);std::cerr<<"  op6 stack projections="<<projs.size()<<"\n";
    for(size_t i=0;i<projs.size();i++)for(size_t j=0;j<projs.size();j++){
      uint64_t combined=combine(projs[i].p,projs[j].p),tops=0;
      if(projs[i].h0)tops=e.set(tops,projs[i].h0-1,0,N);if(projs[i].h1)tops=e.set(tops,projs[i].h1-1,3,N);if(projs[j].h0)tops=e.set(tops,projs[j].h0-1,1,N);if(projs[j].h1)tops=e.set(tops,projs[j].h1-1,2,N);
      enumerate_stacking(combined,tops,[&](uint64_t out,uint64_t){try_add(out);},true);
    }
    return keys.size()-before;
  }

  void bfs(){while(queue_head<keys.size()){while(queue_head<keys.size()){uint32_t k=keys[queue_head++];uint64_t h=e.expand_half(k);op1(h);op2(h);op3(h);record_qual(k,h);}op4_phase();op5_phase();}}
  void dump_bitset(const std::string& path) const {
    const uint64_t nbits = uint64_t(1) << (4*e.L);
    std::vector<uint64_t> words((nbits+63)/64,0);
    for(uint32_t k:keys){
      uint32_t vals[2]={k,e.half_sym_key(k)};
      for(uint32_t v:vals) words[v>>6] |= uint64_t(1)<<(v&63);
    }
    std::ofstream out(path,std::ios::binary);
    uint32_t magic=0x48414c46u, layers=e.L; uint64_t count=0;
    for(uint64_t w:words) count += std::popcount(w);
    out.write(reinterpret_cast<const char*>(&magic),4);
    out.write(reinterpret_cast<const char*>(&layers),4);
    out.write(reinterpret_cast<const char*>(&count),8);
    out.write(reinterpret_cast<const char*>(words.data()),words.size()*8);
  }

  void run(bool skip_op6=false,const std::string& dump_path={}){auto t=std::chrono::steady_clock::now();seeds();std::cerr<<"seeds canonical="<<keys.size()<<"\n";bfs();std::cerr<<"after bfs="<<keys.size()<<"\n";int round=0;if(!skip_op6)while(true){size_t n=op6();std::cerr<<"op6 round "<<round++<<" added="<<n<<" total="<<keys.size()<<"\n";if(!n)break;bfs();std::cerr<<"after rebfs="<<keys.size()<<"\n";}size_t total=0;for(uint32_t k:keys)total+=1+(e.half_sym_key(k)!=k);if(!dump_path.empty())dump_bitset(dump_path);double sec=std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count();std::cout<<"{\"L\":"<<e.L<<",\"canonical\":"<<keys.size()<<",\"total\":"<<total<<",\"seconds\":"<<sec<<"}\n";}
};

} // namespace

int main(int argc,char**argv){
  int L=argc>1?std::stoi(argv[1]):3; bool skip=false; std::string dump;
  for(int i=2;i<argc;i++){std::string a=argv[i];if(a=="--skip-op6")skip=true;else if(a=="--dump"&&i+1<argc)dump=argv[++i];}
  half_oracle::Search s(L);s.run(skip,dump);
}
