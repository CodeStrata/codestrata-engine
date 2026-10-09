package pkg.a;

import pkg.b.Beta;

public final class Alpha {
    public Beta peer() {
        return new Beta();
    }
}
