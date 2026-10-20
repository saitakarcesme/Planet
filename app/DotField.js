// Deterministic irregular packing. The spacing bound also reserves room for
// each dot's independent drift at its largest possible size.
var minimumSeparation = 5.3;
var minimumRadius = 0.24;
var maximumRadius = 1.8;
var maximumDrift = 0.25;

function points(size) {
    var seed = 271828;
    function random() { seed = (seed * 16807) % 2147483647; return (seed-1)/2147483646; }
    var scale=size/48, positions=[];
    for (var count=0; count<48; count++) {
        var best=null, bestDistance=-1;
        for (var attempt=0; attempt<240; attempt++) {
            var angle=random()*Math.PI*2, radius=Math.sqrt(random())*19.8;
            var candidate={x:Math.cos(angle)*radius,y:Math.sin(angle)*radius};
            var nearest=100;
            for (var j=0; j<positions.length; j++) {
                var dx=candidate.x-positions[j].x,dy=candidate.y-positions[j].y;
                nearest=Math.min(nearest,Math.sqrt(dx*dx+dy*dy));
            }
            if (nearest>bestDistance) { bestDistance=nearest; best=candidate; }
        }
        if (positions.length && bestDistance<minimumSeparation) break;
        positions.push(best);
    }
    return positions.map(function(p) {
        return {x:size/2+p.x*scale,y:size/2+p.y*scale,
            cx:size/2,cy:size/2,phase:random()*Math.PI*2,
            tempo:0.82+random()*0.4,peak:0.78+random()*0.22,scale:scale};
    });
}

function radiusAt(dot,time,phase,hovered) {
    var speed=phase === "thinking" ? 3.6 : phase === "acting" ? 4.6 : 2.6;
    var wave=Math.pow(0.5+0.5*Math.sin(time*speed*dot.tempo+dot.phase),0.8);
    if (hovered || phase === "success") wave=Math.min(1,wave+0.1);
    return (minimumRadius+(maximumRadius*dot.peak-minimumRadius)*wave)*dot.scale;
}

function positionAt(dot,time) {
    // Global rotation preserves pairwise distances; bounded local drift makes
    // the motion less mechanical without allowing dots to touch.
    var angle=time*0.16;
    var x=dot.x-dot.cx+Math.cos(time*0.8+dot.phase)*maximumDrift*dot.scale;
    var y=dot.y-dot.cy+Math.sin(time*0.8+dot.phase)*maximumDrift*dot.scale;
    return {x:dot.cx+x*Math.cos(angle)-y*Math.sin(angle),
            y:dot.cy+x*Math.sin(angle)+y*Math.cos(angle)};
}
