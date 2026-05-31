package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// --- tool input schemas ---

type CheckFinesInput struct {
	Plate string `json:"plate" jsonschema:"госномер авто (Кыргызстан), напр. 01KG555BRQ"`
}

type SearchInput struct {
	Query   string `json:"query" jsonschema:"ключевые слова для поиска"`
	PerPage int    `json:"per_page,omitempty" jsonschema:"сколько объявлений запросить (по умолчанию 30)"`
	Strict  *bool  `json:"strict,omitempty" jsonschema:"убрать нерелевантную мешанину (по умолчанию true)"`
}

type SearchCarsInput struct {
	Make        string `json:"make" jsonschema:"марка (определяет категорию), напр. Dodge"`
	Model       string `json:"model,omitempty" jsonschema:"модель, матч по названию, напр. Ram"`
	YearFrom    int    `json:"year_from,omitempty" jsonschema:"год выпуска от"`
	PriceMaxUSD int    `json:"price_max_usd,omitempty" jsonschema:"потолок цены в долларах США"`
	PerPage     int    `json:"per_page,omitempty" jsonschema:"сколько объявлений запросить (по умолчанию 50)"`
}

type SearchRentalsInput struct {
	Rooms         string `json:"rooms,omitempty" jsonschema:"'1'..'4' или 'студия' (пусто = любое)"`
	PriceMax      int    `json:"price_max,omitempty" jsonschema:"потолок цены в СОМАХ"`
	District      string `json:"district,omitempty" jsonschema:"район/микрорайон текстом, напр. '7 микрорайон'"`
	Deal          string `json:"deal,omitempty" jsonschema:"'long' (долгосрочно) или 'daily' (посуточно)"`
	ExcludeShared *bool  `json:"exclude_shared,omitempty" jsonschema:"убрать 'подселение' (по умолчанию true)"`
	PerPage       int    `json:"per_page,omitempty" jsonschema:"размер страницы (по умолчанию 50)"`
}

func boolOr(p *bool, def bool) bool {
	if p == nil {
		return def
	}
	return *p
}

func intOr(v, def int) int {
	if v <= 0 {
		return def
	}
	return v
}

func main() {
	selftest := flag.Bool("selftest", false, "run a live self-test instead of the MCP server")
	flag.Parse()
	if *selftest {
		runSelftest()
		return
	}

	server := mcp.NewServer(&mcp.Implementation{Name: "lalafo-kg", Version: "0.1.0"}, nil)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "check_fines",
		Description: "Проверка штрафов/истории авто по госномеру (Кыргызстан) через Carcheck. Carcheck закрыт логином и reCAPTCHA — инструмент нормализует номер и отдаёт ссылки; вход и капчу проходит пользователь.",
	}, func(ctx context.Context, req *mcp.CallToolRequest, in CheckFinesInput) (*mcp.CallToolResult, FineResult, error) {
		p := normalizePlate(in.Plate)
		return nil, FineResult{
			PlateInput: in.Plate, PlateNormalized: p, ValidFormat: plausiblePlate(p),
			Links: buildLinks(p), Note: carcheckNote,
		}, nil
	})

	mcp.AddTool(server, &mcp.Tool{
		Name:        "search",
		Description: "Поиск объявлений на Lalafo по ключевым словам. strict (по умолчанию true) убирает нерелевантную «мешанину» и сортирует по релевантности.",
	}, func(ctx context.Context, req *mcp.CallToolRequest, in SearchInput) (*mcp.CallToolResult, SearchResult, error) {
		res, err := searchListings(in.Query, intOr(in.PerPage, 30), boolOr(in.Strict, true))
		return nil, res, err
	})

	mcp.AddTool(server, &mcp.Tool{
		Name:        "search_cars",
		Description: "Поиск авто на Lalafo. Марка задаёт категорию, год — диапазон, цена нормализуется в USD (серверный фильтр цены слеп к валюте).",
	}, func(ctx context.Context, req *mcp.CallToolRequest, in SearchCarsInput) (*mcp.CallToolResult, CarsResult, error) {
		return nil, searchCars(in.Make, in.Model, in.YearFrom, in.PriceMaxUSD, intOr(in.PerPage, 50)), nil
	})

	mcp.AddTool(server, &mcp.Tool{
		Name:        "search_rentals",
		Description: "Поиск аренды квартир (Бишкек/КР). rooms '1'..'4' или 'студия'; price_max в СОМАХ; district — район текстом (структурного фильтра нет); deal long|daily; exclude_shared убирает «подселение».",
	}, func(ctx context.Context, req *mcp.CallToolRequest, in SearchRentalsInput) (*mcp.CallToolResult, RentalsResult, error) {
		return nil, searchRentals(in.Rooms, in.PriceMax, in.District, orDefault(in.Deal, "long"),
			boolOr(in.ExcludeShared, true), intOr(in.PerPage, 50)), nil
	})

	if err := server.Run(context.Background(), &mcp.StdioTransport{}); err != nil {
		log.Fatal(err)
	}
}

// runSelftest mirrors the Python selftest: hits the live API and prints results.
func runSelftest() {
	dump := func(v any) {
		b, _ := json.MarshalIndent(v, "", "  ")
		fmt.Println(string(b))
	}

	fmt.Println("== check_fines ==")
	p := normalizePlate("01 kg 555 brq")
	dump(FineResult{PlateInput: "01 kg 555 brq", PlateNormalized: p,
		ValidFormat: plausiblePlate(p), Links: buildLinks(p), Note: carcheckNote})

	fmt.Println("\n== search('koss porta', strict) ==")
	if r, err := searchListings("koss porta", 40, true); err != nil {
		fmt.Println("ERR:", err)
	} else {
		fmt.Printf("hits=%d\n", r.Count)
		for _, it := range r.Items {
			fmt.Printf("  %v %s | %.40s | rel=%v\n", deref(it.Price), it.Currency, it.Title, it.Relevance)
		}
	}

	fmt.Println("\n== search_cars(Dodge Ram, >=2020, <=$30000) ==")
	cr := searchCars("Dodge", "Ram", 2020, 30000, 50)
	fmt.Printf("category_id=%d count=%d warn=%q\n", cr.CategoryID, cr.Count, cr.Warning)
	for _, it := range cr.Items {
		fmt.Printf("  $%v (%s) %d | %.42s\n    %s\n", deref(it.PriceUSD), it.PriceRaw, it.Year, it.Title, it.URL)
	}

	fmt.Println("\n== search_rentals(2-комн, <=40000 сом, 7 микрорайон) ==")
	rr := searchRentals("2", 40000, "7 микрорайон", "long", true, 50)
	fmt.Printf("server-total=%d scanned=%d matched=%d warn=%q\n", rr.ServerTotal, rr.Scanned, rr.Count, rr.Warning)
	for _, it := range rr.Items {
		fmt.Printf("  %v %s | %.42s | %s\n", deref(it.Price), it.Currency, it.Title, it.URL)
	}

	fmt.Println("\nOK")
}

func deref(p *float64) any {
	if p == nil {
		return "—"
	}
	return *p
}
