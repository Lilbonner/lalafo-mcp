package main

import (
	"fmt"
	"math"
	"net/url"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

// --- verified catalog ---
var makeCategory = map[string]int64{"dodge": 1566} // cars are categorized BY BRAND
var rentalCategory = map[string]int64{"long": 2044, "daily": 2045}
var roomValue = map[string]string{ // param 69 "Количество комнат" -> value_id
	"1": "2773", "2": "2774", "3": "2775", "4": "2776",
	"студия": "15496", "studio": "15496", "0": "15496",
}
var sharedMarkers = []string{
	"подселение", "подселением", "подсилен", "подселен", "подселять",
	"одна комната", "для девуш", "для девоч", "для парн", "койко",
}

const yearParam = "parameters[62][from]" // numeric range, literal year
const roomsParam = "parameters[69]"      // categorical -> value_id

var (
	tokenSplitRe = regexp.MustCompile(`[^0-9a-zA-Zа-яА-Я]+`)
	yearRe       = regexp.MustCompile(`(19|20)\d\d`)
	yearGRe      = regexp.MustCompile(`(19|20)\d\d\s*г`) // "looks like a car listing"
	mkrRe        = regexp.MustCompile(`мкр|мкрн|микрорайон|мрн|\bмк\b`)
	digitsRe     = regexp.MustCompile(`\d+`)
)

// --- helpers ---

func tokens(s string) []string {
	var out []string
	for _, t := range tokenSplitRe.Split(strings.ToLower(s), -1) {
		if len([]rune(t)) > 1 {
			out = append(out, t)
		}
	}
	return out
}

func containsAll(hay string, toks []string) bool {
	for _, t := range toks {
		if !strings.Contains(hay, t) {
			return false
		}
	}
	return true
}

func containsAny(hay string, list []string) bool {
	for _, t := range list {
		if strings.Contains(hay, t) {
			return true
		}
	}
	return false
}

func absURL(u string) string {
	if u == "" {
		return ""
	}
	if strings.HasPrefix(u, "http") {
		return u
	}
	return "https://lalafo.kg" + u
}

func pick(a, b string) string {
	if a != "" {
		return a
	}
	return b
}

func orDefault(s, def string) string {
	if strings.TrimSpace(s) == "" {
		return def
	}
	return s
}

func round2(x float64) float64 { return math.Round(x*100) / 100 }

func priceLess(a, b *float64) bool { // nil sorts last
	if a == nil {
		return false
	}
	if b == nil {
		return true
	}
	return *a < *b
}

func priceRaw(a Ad) string {
	if a.Price == nil {
		return "— " + a.Symbol
	}
	return fmt.Sprintf("%g %s", *a.Price, a.Symbol)
}

func toUSD(a Ad, rate float64) *float64 {
	if a.Symbol == "$" || a.Currency == "USD" {
		return a.Price
	}
	if a.NationalPrice != nil && a.NationalPrice.Price != nil {
		v := math.Round(*a.NationalPrice.Price / rate)
		return &v
	}
	return nil
}

func envFloat(key string, def float64) float64 {
	if v, err := strconv.ParseFloat(getenv(key, ""), 64); err == nil && v > 0 {
		return v
	}
	return def
}

// --- output types ---

type Listing struct {
	Title     string   `json:"title"`
	Price     *float64 `json:"price,omitempty"`
	Currency  string   `json:"currency,omitempty"`
	City      string   `json:"city,omitempty"`
	Relevance float64  `json:"relevance"`
	URL       string   `json:"url"`
}
type SearchResult struct {
	Count int       `json:"count"`
	Items []Listing `json:"items"`
}

type CarItem struct {
	Title    string   `json:"title"`
	PriceUSD *float64 `json:"price_usd"`
	PriceRaw string   `json:"price_raw"`
	Year     int      `json:"year,omitempty"`
	URL      string   `json:"url"`
}
type CarsResult struct {
	Make       string    `json:"make"`
	CategoryID int64     `json:"category_id,omitempty"`
	Count      int       `json:"count"`
	Warning    string    `json:"warning,omitempty"`
	Items      []CarItem `json:"items"`
}

type RentalItem struct {
	Title    string   `json:"title"`
	Price    *float64 `json:"price,omitempty"`
	Currency string   `json:"currency,omitempty"`
	City     string   `json:"city,omitempty"`
	URL      string   `json:"url"`
}
type RentalsResult struct {
	Deal           string       `json:"deal"`
	CategoryID     int64        `json:"category_id"`
	Rooms          string       `json:"rooms"`
	ServerTotal    int          `json:"total_matching_server_filters"`
	Scanned        int          `json:"scanned"`
	Count          int          `json:"count"`
	DistrictFilter string       `json:"district_filter,omitempty"`
	Note           string       `json:"note,omitempty"`
	Warning        string       `json:"warning,omitempty"`
	Items          []RentalItem `json:"items"`
}

// --- logic ---

func searchListings(query string, perPage int, strict bool) (SearchResult, error) {
	p := url.Values{}
	p.Set("q", query)
	p.Set("per-page", strconv.Itoa(perPage))
	p.Set("expand", "url,description")
	sr, err := apiSearch(p)
	if err != nil {
		return SearchResult{}, err
	}
	toks := tokens(query)
	seen := map[int64]bool{}
	out := []Listing{}
	for _, a := range sr.Items {
		if seen[a.ID] {
			continue
		}
		seen[a.ID] = true
		hay := strings.ToLower(a.Title + " " + a.Description)
		matched := 0
		for _, t := range toks {
			if strings.Contains(hay, t) {
				matched++
			}
		}
		cov := 0.0
		if len(toks) > 0 {
			cov = float64(matched) / float64(len(toks))
		}
		if strict && cov == 0 { // drop pure "mishmash" (0 query tokens)
			continue
		}
		out = append(out, Listing{
			Title: a.Title, Price: a.Price, Currency: pick(a.Symbol, a.Currency),
			City: a.City, Relevance: round2(cov), URL: absURL(a.URL),
		})
	}
	sort.SliceStable(out, func(i, j int) bool { return out[i].Relevance > out[j].Relevance })
	return SearchResult{Count: len(out), Items: out}, nil
}

func resolveMakeCategory(make string) int64 {
	key := strings.ToLower(strings.TrimSpace(make))
	if c, ok := makeCategory[key]; ok {
		return c
	}
	p := url.Values{}
	p.Set("q", make)
	p.Set("per-page", "40")
	sr, err := apiSearch(p)
	if err != nil {
		return 0
	}
	counts := map[int64]int{}
	for _, a := range sr.Items {
		if strings.HasPrefix(strings.ToLower(a.Title), key) && yearGRe.MatchString(a.Title) {
			counts[a.CategoryID]++
		}
	}
	best, bestN := int64(0), 0
	for c, n := range counts {
		if n > bestN {
			best, bestN = c, n
		}
	}
	return best
}

// narrowWarning flags a silently-ignored structured filter (totalCount unchanged).
func narrowWarning(cat int64, total int, what string) string {
	bp := url.Values{}
	bp.Set("category_id", strconv.FormatInt(cat, 10))
	bp.Set("per-page", "1")
	if base, err := apiSearch(bp); err == nil && base.Meta.TotalCount == total {
		return "Фильтр по " + what + " мог не примениться (totalCount не изменился)."
	}
	return ""
}

func searchCars(make, model string, yearFrom, priceMaxUSD, perPage int) CarsResult {
	cat := resolveMakeCategory(make)
	if cat == 0 {
		return CarsResult{Make: make, Items: []CarItem{},
			Warning: "Не удалось определить категорию для марки '" + make + "'."}
	}
	p := url.Values{}
	p.Set("category_id", strconv.FormatInt(cat, 10))
	p.Set("per-page", strconv.Itoa(perPage))
	p.Set("expand", "url")
	if yearFrom > 0 {
		p.Set(yearParam, strconv.Itoa(yearFrom))
	}
	sr, err := apiSearch(p)
	if err != nil {
		return CarsResult{Make: make, CategoryID: cat, Items: []CarItem{}, Warning: err.Error()}
	}
	warning := ""
	if yearFrom > 0 {
		warning = narrowWarning(cat, sr.Meta.TotalCount, "году")
	}
	rate := envFloat("USD_KGS_RATE", 89)
	mtoks := tokens(model)
	seen := map[int64]bool{}
	rows := []CarItem{}
	for _, a := range sr.Items {
		if seen[a.ID] {
			continue
		}
		seen[a.ID] = true
		if !containsAll(strings.ToLower(a.Title), mtoks) {
			continue
		}
		usd := toUSD(a, rate)
		if priceMaxUSD > 0 && (usd == nil || *usd > float64(priceMaxUSD)) {
			continue
		}
		yr := 0
		if m := yearRe.FindString(a.Title); m != "" {
			yr, _ = strconv.Atoi(m)
		}
		rows = append(rows, CarItem{Title: a.Title, PriceUSD: usd, PriceRaw: priceRaw(a), Year: yr, URL: absURL(a.URL)})
	}
	sort.SliceStable(rows, func(i, j int) bool { return priceLess(rows[i].PriceUSD, rows[j].PriceUSD) })
	return CarsResult{Make: make, CategoryID: cat, Count: len(rows), Warning: warning, Items: rows}
}

func districtMatcher(district string) func(string) bool {
	d := strings.ToLower(strings.TrimSpace(district))
	if d == "" {
		return func(string) bool { return true }
	}
	num := digitsRe.FindString(d)
	if num != "" && mkrRe.MatchString(d) {
		// RE2 has no lookaround; bound the number with start/non-digit on each side.
		rx := regexp.MustCompile(
			`(^|[^0-9])` + num + `\s*-?\s*(мкр|мкрн|мк|мрн|микрорайон)` +
				`|(мкр|мкрн|мк|мрн|микрорайон)\s*-?\s*` + num + `($|[^0-9])`)
		return func(hay string) bool { return rx.MatchString(hay) }
	}
	toks := tokens(d)
	return func(hay string) bool { return containsAll(hay, toks) }
}

func searchRentals(rooms string, priceMax int, district, deal string, excludeShared bool, perPage int) RentalsResult {
	dealKey := strings.ToLower(strings.TrimSpace(orDefault(deal, "long")))
	cat, ok := rentalCategory[dealKey]
	if !ok {
		return RentalsResult{Items: []RentalItem{}, Warning: "Неизвестный тип сделки (long|daily)."}
	}
	base := url.Values{}
	base.Set("category_id", strconv.FormatInt(cat, 10))
	base.Set("expand", "url,description")
	base.Set("per-page", strconv.Itoa(perPage))
	roomVID := ""
	if strings.TrimSpace(rooms) != "" {
		v, ok := roomValue[strings.ToLower(strings.TrimSpace(rooms))]
		if !ok {
			return RentalsResult{Items: []RentalItem{}, Warning: "Неизвестное число комнат (1-4 или 'студия')."}
		}
		roomVID = v
		base.Set(roomsParam, v)
	}
	if priceMax > 0 {
		base.Set("price[from]", "0")
		base.Set("price[to]", strconv.Itoa(priceMax))
	}

	withPage := func(page int) url.Values {
		c := url.Values{}
		for k, vs := range base {
			c[k] = append([]string(nil), vs...)
		}
		c.Set("page", strconv.Itoa(page))
		return c
	}

	first, err := apiSearch(withPage(1))
	if err != nil {
		return RentalsResult{Items: []RentalItem{}, Warning: err.Error()}
	}
	total := first.Meta.TotalCount
	warning := ""
	if roomVID != "" {
		warning = narrowWarning(cat, total, "комнатам")
	}

	match := districtMatcher(district)
	const maxScan = 200
	seen := map[int64]bool{}
	rows := []RentalItem{}
	scanned, page := 0, 1
	items := first.Items
	for len(items) > 0 && scanned < maxScan {
		for _, a := range items {
			if seen[a.ID] {
				continue
			}
			seen[a.ID] = true
			scanned++
			hay := strings.ToLower(a.Title + " " + a.Description)
			if excludeShared && containsAny(hay, sharedMarkers) {
				continue
			}
			if !match(hay) {
				continue
			}
			rows = append(rows, RentalItem{
				Title: a.Title, Price: a.Price, Currency: pick(a.Symbol, a.Currency),
				City: a.City, URL: absURL(a.URL),
			})
		}
		if scanned >= total || scanned >= maxScan {
			break
		}
		page++
		time.Sleep(250 * time.Millisecond) // light pacing between paginated requests
		nxt, e := apiSearch(withPage(page))
		if e != nil {
			break
		}
		items = nxt.Items
	}
	sort.SliceStable(rows, func(i, j int) bool { return priceLess(rows[i].Price, rows[j].Price) })

	res := RentalsResult{
		Deal: orDefault(deal, "long"), CategoryID: cat, Rooms: orDefault(rooms, "any"),
		ServerTotal: total, Scanned: scanned, Count: len(rows), Items: rows,
	}
	if district != "" {
		res.DistrictFilter = district
		res.Note = "Район отфильтрован по тексту; объявления без слова о районе могли не попасть."
	}
	if warning != "" {
		res.Warning = warning
	}
	return res
}
