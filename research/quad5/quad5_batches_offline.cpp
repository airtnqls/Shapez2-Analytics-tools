#define main quad5_batches_old_main
#include "/mnt/data/work_basis/quad5_batches.cpp"
#undef main
#include <map>

struct Collector {
  std::unordered_map<U,U> parent;
  uint64_t nodes=0;
  void add(U pushed,U pre){
    if(!pushed||sw(pushed))return;
    U c=canon(pushed);
    auto it=parent.find(c);
    if(it==parent.end()||pre<it->second)parent[c]=pre;
  }
  void enumerate(U seed){
    if((seed>>(8*(L-1))&255)==0 || [&](){for(int c=0;c<4;c++)if(cell(seed,L-1,c)==C)return false;return true;}()){
      nodes++;add(pp(seed),seed);return;
    }
    auto initial=prep(seed);
    auto rec=[&](auto&&self,U s,int l,uint32_t gaps,uint32_t hint)->void{
      nodes++;
      auto pr=prep(s); auto g=grav(pr.shifted,hint); add(g.s,s);
      if(l>=L-1)return;
      if(occ(pr.shifted)==g.sup&&gaps==0)return;
      uint32_t child=gaps;if(l>0)child&=~(15u<<(4*(l-1)));
      for(U row:lt.get(s,l))self(self,s|(row<<(8*l)),l+1,child,g.sup);
    };
    rec(rec,seed,0,initial.gaps,0);
  }
};
static int material(U s){int n=0;for(int l=0;l<L;l++)for(int c=0;c<4;c++)n+=cell(s,l,c)!=0;return n;}
static std::vector<U> reduce_candidates(std::unordered_map<U,U>&cand,const std::unordered_set<U>&earlier,std::unordered_set<U>&all,U batch,std::unordered_map<U,std::pair<U,int>>&parents){
  std::vector<U> order;order.reserve(cand.size());for(auto&[x,p]:cand)order.push_back(x);
  std::sort(order.begin(),order.end(),[](U a,U b){int pa=material(a),pb=material(b);return pa!=pb?pa<pb:a<b;});
  std::vector<U> out;out.reserve(order.size());
  // all initially contains earlier batches only.  New essentials are inserted in strict material order.
  for(U x:order){
    if(stackable(x,all))continue;
    all.insert(x);out.push_back(x);parents[x]={cand[x],(int)batch};
  }
  return out;
}
int main(){
 init_hok();
 std::vector<U>base;{std::ifstream f("/mnt/data/work_basis/quad5_base_halves.bin",std::ios::binary);U x;while(f.read((char*)&x,8))base.push_back(x);}
 int nt=std::max(1u,std::thread::hardware_concurrency());
 std::cerr<<"base="<<base.size()<<" threads="<<nt<<"\n";
 auto collect_seed_pairs=[&](){
   std::vector<std::unordered_map<U,U>> local(nt);std::vector<uint64_t> node(nt);std::atomic<size_t>next{0};std::vector<std::thread>ths;
   for(int ti=0;ti<nt;ti++)ths.emplace_back([&,ti]{Collector c;c.parent.reserve(100000);while(1){size_t i=next.fetch_add(1);if(i>=base.size())break;U e=base[i];for(size_t j=i;j<base.size();j++){U w0=base[j];for(int z=0;z<2;z++){U w=z?hsym(w0):w0;if(z&&w==w0)continue;U full=e|west(w);if(full&&minimal(full,e,w))c.enumerate(full);}}if(i%200==0)std::cerr<<"\rpair "<<i<<"/"<<base.size()<<std::flush;}local[ti]=std::move(c.parent);node[ti]=c.nodes;});for(auto&t:ths)t.join();std::cerr<<"\n";
   std::unordered_map<U,U> merged;size_t reserve=0;uint64_t nodes=0;for(auto&x:local)reserve+=x.size();merged.reserve(reserve);for(int i=0;i<nt;i++){nodes+=node[i];for(auto&[x,p]:local[i]){auto it=merged.find(x);if(it==merged.end()||p<it->second)merged[x]=p;}}
   std::cerr<<"candidate unique="<<merged.size()<<" nodes="<<nodes<<"\n";return merged;
 };
 auto collect_seeds=[&](const std::vector<U>&seeds){
   std::vector<std::unordered_map<U,U>> local(nt);std::vector<uint64_t> node(nt);std::atomic<size_t>next{0};std::vector<std::thread>ths;
   for(int ti=0;ti<nt;ti++)ths.emplace_back([&,ti]{Collector c;c.parent.reserve(seeds.size()/nt+100);while(1){size_t i=next.fetch_add(1);if(i>=seeds.size())break;c.enumerate(seeds[i]);}local[ti]=std::move(c.parent);node[ti]=c.nodes;});for(auto&t:ths)t.join();
   std::unordered_map<U,U> merged;size_t reserve=0;uint64_t nodes=0;for(auto&x:local)reserve+=x.size();merged.reserve(reserve);for(int i=0;i<nt;i++){nodes+=node[i];for(auto&[x,p]:local[i]){auto it=merged.find(x);if(it==merged.end()||p<it->second)merged[x]=p;}}
   std::cerr<<"candidate unique="<<merged.size()<<" nodes="<<nodes<<"\n";return merged;
 };
 auto started=std::chrono::steady_clock::now();
 std::unordered_set<U> all;all.reserve(100000);std::unordered_map<U,std::pair<U,int>>parents;
 auto cand=collect_seed_pairs();std::unordered_set<U>empty;auto cur=reduce_candidates(cand,empty,all,0,parents);std::cout<<"batch 0 candidates="<<cand.size()<<" essential="<<cur.size()<<" total="<<all.size()<<"\n";
 for(int b=1;b<16&&!cur.empty();b++){auto c=collect_seeds(cur);auto nx=reduce_candidates(c,all,all,b,parents);std::cout<<"batch "<<b<<" candidates="<<c.size()<<" essential="<<nx.size()<<" total="<<all.size()<<"\n";cur.swap(nx);}
 std::array<size_t,16>d{};for(auto&[x,p]:parents)d[p.second]++;for(int i=0;i<16;i++)if(d[i])std::cout<<"parent_batch["<<i<<"]="<<d[i]<<"\n";std::cout<<"seconds="<<std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count()<<"\n";
 std::ofstream f("/mnt/data/work_basis/quad5_pp_parents_offline.tsv");for(U x:all){auto p=parents[x];f<<p.second<<'\t'<<code(x)<<'\t'<<code(p.first)<<'\n';}
}
