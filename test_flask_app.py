"""
Quick test script to verify Flask app functionality
Run this AFTER starting the Flask app (python3 app.py)
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_homepage():
    """Test homepage loads"""
    print("="*60)
    print("Test 1: Homepage")
    print("="*60)
    try:
        response = requests.get(BASE_URL)
        if response.status_code == 200:
            print("✅ Homepage loads successfully (200 OK)")
            print(f"   Content length: {len(response.text)} bytes")
        else:
            print(f"❌ Failed with status code: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_parse_api():
    """Test parse API endpoint"""
    print("\n" + "="*60)
    print("Test 2: Parse API")
    print("="*60)

    test_data = {
        "address": "NGO394 DOI CAN P.CONG VI BD HN",
        "province": "Hà Nội",
        "district": None,
        "cif_no": "TEST_CIF_001"
    }

    print(f"Sending request to {BASE_URL}/parse")
    print(f"Payload: {json.dumps(test_data, indent=2)}")

    try:
        response = requests.post(
            f"{BASE_URL}/parse",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ Parse API works!")
                print(f"   - Ward: {result['summary']['ward']}")
                print(f"   - District: {result['summary']['district']}")
                print(f"   - Province: {result['summary']['province']}")
                print(f"   - Confidence: {result['summary']['confidence']:.2f}")
                print(f"   - Processing time: {result['metadata']['total_time_ms']:.1f}ms")
                return True
            else:
                print(f"❌ API returned success=False: {result.get('error')}")
                return False
        else:
            print(f"❌ Failed with status code: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_random_api():
    """Test random address API"""
    print("\n" + "="*60)
    print("Test 3: Random Address API")
    print("="*60)

    try:
        response = requests.get(f"{BASE_URL}/random")

        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ Random API works!")
                print(f"   - CIF: {result['data']['cif_no']}")
                print(f"   - Address: {result['data']['address'][:60]}...")
                print(f"   - Province: {result['data']['province']}")
                return True
            else:
                print(f"❌ API returned success=False: {result.get('error')}")
                return False
        else:
            print(f"❌ Failed with status code: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_stats_page():
    """Test stats page loads"""
    print("\n" + "="*60)
    print("Test 4: Statistics Page")
    print("="*60)
    try:
        response = requests.get(f"{BASE_URL}/stats")
        if response.status_code == 200:
            print("✅ Stats page loads successfully (200 OK)")
            print(f"   Content length: {len(response.text)} bytes")
        else:
            print(f"❌ Failed with status code: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("\n" + "🧪 Testing Flask App" + "\n")
    print("⚠️  Make sure Flask app is running first:")
    print("   Run: python3 app.py")
    print()

    input("Press Enter to start tests...")

    results = []

    # Run tests
    results.append(("Homepage", test_homepage()))
    results.append(("Parse API", test_parse_api()))
    results.append(("Random API", test_random_api()))
    results.append(("Stats Page", test_stats_page()))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Flask app is working correctly!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check the output above for details.")

if __name__ == "__main__":
    main()
