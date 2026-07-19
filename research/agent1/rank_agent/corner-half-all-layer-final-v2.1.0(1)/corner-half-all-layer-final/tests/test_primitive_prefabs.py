from corner_half.primitive_prefabs import (
    build_crystal_trigger,
    build_layer_stack,
    build_one_pin,
    build_pin_tower_helper,
    build_single_crystal_helper,
    build_single_layer_pattern,
)


def main():
    for mask in range(16):
        c=build_single_layer_pattern(mask)
        assert c.replay_ok,(mask,c)
    for cap in range(1,13):
        for q in range(4):
            c=build_one_pin(cap,q)
            assert c.replay_ok,(cap,q,c)
        t=build_crystal_trigger(cap)
        assert t.replay_ok,(cap,t)
        for h in range(1,cap+1):
            for layer in {0,h-1,h//2}:
                c=build_single_crystal_helper(cap,h,layer)
                assert c.replay_ok,(cap,h,layer,c)
                p=build_pin_tower_helper(cap,h,layer)
                assert p.replay_ok,(cap,h,layer,p)
    print({'single_layer_masks':16,'pin_caps':12,'pin_orientations':4})

if __name__=='__main__':main()
