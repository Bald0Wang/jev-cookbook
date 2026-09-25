from scripts.analyze_combinations import combine, ece, percentile

def test_percentile_and_ece():
    assert percentile([1,2,3], .5)==2
    rows=[{"probs":{"a":.8,"b":.2},"expected":"a"},{"probs":{"a":.8,"b":.2},"expected":"b"}]
    assert abs(ece(rows)-.3)<1e-12

def test_probability_and_majority_combine():
    task={"labels":["a","b"]}; members=[{"probs":{"a":.9,"b":.1}},{"probs":{"a":.2,"b":.8}},{"probs":{"a":.6,"b":.4}}]
    p,pred=combine(task,members,"probability_average",[1,1,1]); assert pred=="a" and abs(p["a"]-.5666666667)<1e-9
    p,pred=combine(task,members,"majority",[1,1,1]); assert pred=="a" and p["a"]==2/3
