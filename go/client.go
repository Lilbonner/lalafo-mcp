package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

const apiBase = "https://api.lalafo.com"

var httpClient = &http.Client{Timeout: 25 * time.Second}

var retryHTTP = map[int]bool{429: true, 500: true, 502: true, 503: true, 504: true}

func getenv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

// headers: country-id / device / language are mandatory (otherwise the API returns 417).
func headers() map[string]string {
	return map[string]string{
		"country-id": getenv("LALAFO_COUNTRY_ID", "12"),
		"device":     "pc",
		"language":   getenv("LALAFO_LANGUAGE", "ru"),
		"Accept":     "application/json, text/plain, */*",
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " +
			"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
	}
}

// apiGetBytes performs a GET with retries on transient network/server errors
// (e.g. connection resets, HTTP 429/5xx) with linear backoff.
func apiGetBytes(path string, params url.Values) ([]byte, error) {
	full := apiBase + path
	if len(params) > 0 {
		full += "?" + params.Encode()
	}
	var lastErr error
	for attempt := 0; attempt < 3; attempt++ {
		if attempt > 0 {
			time.Sleep(time.Duration(600*attempt) * time.Millisecond)
		}
		req, err := http.NewRequest(http.MethodGet, full, nil)
		if err != nil {
			return nil, err
		}
		for k, v := range headers() {
			req.Header.Set(k, v)
		}
		resp, err := httpClient.Do(req)
		if err != nil { // transient network error -> retry
			lastErr = err
			continue
		}
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if retryHTTP[resp.StatusCode] {
			lastErr = fmt.Errorf("http %d", resp.StatusCode)
			continue
		}
		if resp.StatusCode >= 400 {
			return nil, fmt.Errorf("http %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
		}
		return body, nil
	}
	if lastErr == nil {
		lastErr = errors.New("request failed")
	}
	return nil, lastErr
}

// --- typed responses ---

type NationalPrice struct {
	Price *float64 `json:"price"`
}

type Ad struct {
	ID            int64          `json:"id"`
	Title         string         `json:"title"`
	Description   string         `json:"description"`
	Price         *float64       `json:"price"`
	Symbol        string         `json:"symbol"`
	Currency      string         `json:"currency"`
	City          string         `json:"city"`
	CategoryID    int64          `json:"category_id"`
	URL           string         `json:"url"`
	NationalPrice *NationalPrice `json:"national_price"`
}

type SearchResponse struct {
	Items []Ad `json:"items"`
	Meta  struct {
		TotalCount int `json:"totalCount"`
	} `json:"_meta"`
}

func apiSearch(params url.Values) (*SearchResponse, error) {
	if params.Get("page") == "" {
		params.Set("page", "1")
	}
	if params.Get("per-page") == "" {
		params.Set("per-page", "20")
	}
	if params.Get("expand") == "" {
		params.Set("expand", "url")
	}
	raw, err := apiGetBytes("/v3/ads/search", params)
	if err != nil {
		return nil, err
	}
	var sr SearchResponse
	if err := json.Unmarshal(raw, &sr); err != nil {
		return nil, err
	}
	return &sr, nil
}
